import fs from "node:fs";
import path from "node:path";

const COMPONENT_BYTES = {
  5120: 1,
  5121: 1,
  5122: 2,
  5123: 2,
  5125: 4,
  5126: 4,
};

const TYPE_COMPONENTS = {
  SCALAR: 1,
  VEC2: 2,
  VEC3: 3,
  VEC4: 4,
  MAT2: 4,
  MAT3: 9,
  MAT4: 16,
};

function readGlb(filePath) {
  const buffer = fs.readFileSync(filePath);
  if (buffer.readUInt32LE(0) !== 0x46546c67) {
    throw new Error(`${filePath} is not a GLB file`);
  }

  const jsonLength = buffer.readUInt32LE(12);
  const json = JSON.parse(buffer.slice(20, 20 + jsonLength).toString("utf8").trim());
  const binHeaderOffset = 20 + jsonLength;
  const binLength = buffer.readUInt32LE(binHeaderOffset);
  const binStart = binHeaderOffset + 8;
  const bin = buffer.slice(binStart, binStart + binLength);

  return { json, bin };
}

function readAccessor(glb, accessorIndex) {
  const accessor = glb.json.accessors[accessorIndex];
  const view = glb.json.bufferViews[accessor.bufferView];
  const componentCount = TYPE_COMPONENTS[accessor.type];
  const bytesPerComponent = COMPONENT_BYTES[accessor.componentType];
  const stride = view.byteStride || componentCount * bytesPerComponent;
  const offset = (view.byteOffset || 0) + (accessor.byteOffset || 0);
  const rows = [];

  for (let rowIndex = 0; rowIndex < accessor.count; rowIndex += 1) {
    const row = [];
    const base = offset + rowIndex * stride;
    for (let component = 0; component < componentCount; component += 1) {
      const cursor = base + component * bytesPerComponent;
      if (accessor.componentType === 5126) row.push(glb.bin.readFloatLE(cursor));
      else if (accessor.componentType === 5125) row.push(glb.bin.readUInt32LE(cursor));
      else if (accessor.componentType === 5123) row.push(glb.bin.readUInt16LE(cursor));
      else if (accessor.componentType === 5122) row.push(glb.bin.readInt16LE(cursor));
      else if (accessor.componentType === 5121) row.push(glb.bin.readUInt8(cursor));
      else if (accessor.componentType === 5120) row.push(glb.bin.readInt8(cursor));
    }
    rows.push(row);
  }

  return rows;
}

function buildParentIndex(nodes) {
  const parents = Array(nodes.length).fill(-1);
  nodes.forEach((node, index) => {
    for (const child of node.children || []) parents[child] = index;
  });
  return parents;
}

function auditFile(filePath) {
  const glb = readGlb(filePath);
  const { json } = glb;
  const skin = json.skins?.[0];
  const jointNames = skin ? skin.joints.map((index) => json.nodes[index]?.name || `node_${index}`) : [];
  const parents = buildParentIndex(json.nodes || []);

  const sceneRoots = (json.scenes?.[json.scene || 0]?.nodes || []).map((index) => json.nodes[index]?.name || `node_${index}`);
  const meshRoots = sceneRoots.filter((name) => name.startsWith("node_")).length;
  const duplicateJoints = jointNames.filter((name, index) => jointNames.indexOf(name) !== index);
  const unreachableJoints = [];

  if (skin) {
    for (const jointIndex of skin.joints) {
      let cursor = jointIndex;
      const seen = new Set();
      let reachesRoot = false;
      while (cursor >= 0 && !seen.has(cursor)) {
        if (json.nodes[cursor]?.name === "root") {
          reachesRoot = true;
          break;
        }
        seen.add(cursor);
        cursor = parents[cursor];
      }
      if (!reachesRoot) unreachableJoints.push(json.nodes[jointIndex]?.name || `node_${jointIndex}`);
    }
  }

  let primitives = 0;
  let skinnedPrimitives = 0;
  let vertices = 0;
  let morphPrimitives = 0;
  let morphTargets = 0;
  let badWeightRows = 0;
  let weightRows = 0;
  let minWeightSum = Number.POSITIVE_INFINITY;
  let maxWeightSum = Number.NEGATIVE_INFINITY;
  let usesOverFourInfluences = false;

  for (const mesh of json.meshes || []) {
    for (const primitive of mesh.primitives || []) {
      primitives += 1;
      const attrs = primitive.attributes || {};
      if (attrs.POSITION !== undefined) vertices += json.accessors[attrs.POSITION].count;
      if (primitive.targets) {
        morphPrimitives += 1;
        morphTargets += primitive.targets.length;
      }
      if (attrs.JOINTS_0 !== undefined && attrs.WEIGHTS_0 !== undefined) {
        skinnedPrimitives += 1;
        const weights = readAccessor(glb, attrs.WEIGHTS_0);
        weightRows += weights.length;
        for (const row of weights) {
          const sum = row.reduce((acc, value) => acc + value, 0);
          minWeightSum = Math.min(minWeightSum, sum);
          maxWeightSum = Math.max(maxWeightSum, sum);
          if (Math.abs(sum - 1) > 0.02) badWeightRows += 1;
        }
        if (attrs.JOINTS_1 !== undefined || attrs.WEIGHTS_1 !== undefined) usesOverFourInfluences = true;
      }
    }
  }

  const morphNames = [];
  for (const mesh of json.meshes || []) {
    if (Array.isArray(mesh.extras?.targetNames)) morphNames.push(...mesh.extras.targetNames);
  }

  return {
    file: path.normalize(filePath),
    generator: json.asset?.generator || json.asset?.version || "",
    nodes: (json.nodes || []).length,
    meshes: (json.meshes || []).length,
    primitives,
    vertices,
    skins: (json.skins || []).length,
    joints: jointNames.length,
    animations: (json.animations || []).length,
    morphPrimitives,
    morphTargets,
    morphNames,
    sceneRoots,
    meshRoots,
    skeletonRoot: skin?.skeleton !== undefined ? json.nodes[skin.skeleton]?.name || `node_${skin.skeleton}` : null,
    jointNames,
    firstJoints: jointNames.slice(0, 20),
    lastJoints: jointNames.slice(-10),
    duplicateJoints,
    unreachableJoints,
    weightRows,
    badWeightRows,
    minWeightSum: Number.isFinite(minWeightSum) ? Number(minWeightSum.toFixed(5)) : null,
    maxWeightSum: Number.isFinite(maxWeightSum) ? Number(maxWeightSum.toFixed(5)) : null,
    usesOverFourInfluences,
    extras: json.extras || {},
  };
}

function compareRigs(results) {
  const comparisons = [];
  for (let left = 0; left < results.length; left += 1) {
    for (let right = left + 1; right < results.length; right += 1) {
      const leftNames = results[left].jointNames;
      const rightNames = results[right].jointNames;
      const orderedPrefix = leftNames
        .slice(0, Math.min(leftNames.length, rightNames.length))
        .filter((name, index) => name === rightNames[index])
        .length;
      comparisons.push({
        left: results[left].file,
        right: results[right].file,
        orderedPrefix,
        comparedPrefixLength: Math.min(leftNames.length, rightNames.length),
        missingRight: leftNames.filter((name) => !rightNames.includes(name)),
        missingLeft: rightNames.filter((name) => !leftNames.includes(name)),
      });
    }
  }
  return comparisons;
}

const files = process.argv.slice(2);
if (files.length === 0) {
  console.error("Usage: node tools/audit_glb_rigs.mjs <avatar.glb> [...more.glb]");
  process.exit(2);
}

const results = files.map(auditFile);
console.log(JSON.stringify({ results, comparisons: compareRigs(results) }, null, 2));
