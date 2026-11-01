/*!
Voxel Engine Core for PubCast AI Renderer

High-performance voxel rendering system with:
- Chunk-based world management
- Efficient voxel storage and culling
- GPU-optimized mesh generation
- Real-time world streaming
*/

use nalgebra::{Vector3, Point3};
use std::collections::HashMap;
use wgpu::util::DeviceExt;

/// Size of a voxel chunk (must be power of 2 for optimization)
pub const CHUNK_SIZE: usize = 32;
pub const CHUNK_VOLUME: usize = CHUNK_SIZE * CHUNK_SIZE * CHUNK_SIZE;

/// Voxel data type
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Voxel {
    pub material_id: u8,
    pub density: u8, // 0 = empty, 255 = solid
    pub color: [u8; 3], // RGB color
    pub metadata: u8, // For future use (lighting, etc.)
}

impl Default for Voxel {
    fn default() -> Self {
        Self {
            material_id: 0,
            density: 0,
            color: [128, 128, 128],
            metadata: 0,
        }
    }
}

impl Voxel {
    pub fn new(material_id: u8, density: u8, color: [u8; 3]) -> Self {
        Self {
            material_id,
            density,
            color,
            metadata: 0,
        }
    }
    
    pub fn is_solid(&self) -> bool {
        self.density > 0
    }
    
    pub fn is_empty(&self) -> bool {
        self.density == 0
    }
}

/// 3D position of a chunk in world space
#[derive(Clone, Copy, Debug, Hash, PartialEq, Eq)]
pub struct ChunkCoord {
    pub x: i32,
    pub y: i32,
    pub z: i32,
}

impl ChunkCoord {
    pub fn new(x: i32, y: i32, z: i32) -> Self {
        Self { x, y, z }
    }
    
    pub fn from_world_pos(world_pos: Point3<f32>) -> Self {
        Self {
            x: (world_pos.x / CHUNK_SIZE as f32).floor() as i32,
            y: (world_pos.y / CHUNK_SIZE as f32).floor() as i32,
            z: (world_pos.z / CHUNK_SIZE as f32).floor() as i32,
        }
    }
    
    pub fn to_world_pos(&self) -> Point3<f32> {
        Point3::new(
            self.x as f32 * CHUNK_SIZE as f32,
            self.y as f32 * CHUNK_SIZE as f32,
            self.z as f32 * CHUNK_SIZE as f32,
        )
    }
}

/// A chunk of voxels
pub struct VoxelChunk {
    pub coord: ChunkCoord,
    pub voxels: Box<[Voxel; CHUNK_VOLUME]>,
    pub mesh: Option<ChunkMesh>,
    pub dirty: bool, // Needs mesh regeneration
    pub loaded: bool,
}

impl VoxelChunk {
    pub fn new(coord: ChunkCoord) -> Self {
        Self {
            coord,
            voxels: Box::new([Voxel::default(); CHUNK_VOLUME]),
            mesh: None,
            dirty: true,
            loaded: false,
        }
    }
    
    /// Convert 3D coordinates to 1D array index
    #[inline]
    pub fn coord_to_index(x: usize, y: usize, z: usize) -> usize {
        x + y * CHUNK_SIZE + z * CHUNK_SIZE * CHUNK_SIZE
    }
    
    /// Convert 1D array index to 3D coordinates
    #[inline]
    pub fn index_to_coord(index: usize) -> (usize, usize, usize) {
        let z = index / (CHUNK_SIZE * CHUNK_SIZE);
        let y = (index % (CHUNK_SIZE * CHUNK_SIZE)) / CHUNK_SIZE;
        let x = index % CHUNK_SIZE;
        (x, y, z)
    }
    
    /// Get voxel at local chunk coordinates
    pub fn get_voxel(&self, x: usize, y: usize, z: usize) -> Option<&Voxel> {
        if x >= CHUNK_SIZE || y >= CHUNK_SIZE || z >= CHUNK_SIZE {
            return None;
        }
        let index = Self::coord_to_index(x, y, z);
        Some(&self.voxels[index])
    }
    
    /// Set voxel at local chunk coordinates
    pub fn set_voxel(&mut self, x: usize, y: usize, z: usize, voxel: Voxel) {
        if x >= CHUNK_SIZE || y >= CHUNK_SIZE || z >= CHUNK_SIZE {
            return;
        }
        let index = Self::coord_to_index(x, y, z);
        self.voxels[index] = voxel;
        self.dirty = true;
    }
    
    /// Fill chunk with test pattern
    pub fn fill_test_pattern(&mut self) {
        for x in 0..CHUNK_SIZE {
            for y in 0..CHUNK_SIZE {
                for z in 0..CHUNK_SIZE {
                    // Create a simple test pattern
                    if y < 8 || (x + y + z) % 4 == 0 {
                        let color = [
                            (x * 8) as u8,
                            (y * 8) as u8,
                            (z * 8) as u8,
                        ];
                        self.set_voxel(x, y, z, Voxel::new(1, 255, color));
                    }
                }
            }
        }
        self.dirty = true;
    }
    
    /// Check if chunk is empty (all air)
    pub fn is_empty(&self) -> bool {
        self.voxels.iter().all(|voxel| voxel.is_empty())
    }
}

/// Mesh data for a voxel chunk
#[derive(Debug)]
pub struct ChunkMesh {
    pub vertices: Vec<VoxelVertex>,
    pub indices: Vec<u32>,
    pub vertex_buffer: Option<wgpu::Buffer>,
    pub index_buffer: Option<wgpu::Buffer>,
    pub dirty: bool,
}

impl ChunkMesh {
    pub fn new() -> Self {
        Self {
            vertices: Vec::new(),
            indices: Vec::new(),
            vertex_buffer: None,
            index_buffer: None,
            dirty: true,
        }
    }
    
    pub fn create_gpu_buffers(&mut self, device: &wgpu::Device) {
        if !self.vertices.is_empty() {
            self.vertex_buffer = Some(device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
                label: Some("Chunk Vertex Buffer"),
                contents: bytemuck::cast_slice(&self.vertices),
                usage: wgpu::BufferUsages::VERTEX,
            }));
        }
        
        if !self.indices.is_empty() {
            self.index_buffer = Some(device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
                label: Some("Chunk Index Buffer"),
                contents: bytemuck::cast_slice(&self.indices),
                usage: wgpu::BufferUsages::INDEX,
            }));
        }
        
        self.dirty = false;
    }
}

/// Vertex data for voxel rendering
#[repr(C)]
#[derive(Copy, Clone, Debug, bytemuck::Pod, bytemuck::Zeroable)]
pub struct VoxelVertex {
    pub position: [f32; 3],
    pub normal: [f32; 3],
    pub color: [f32; 3],
    pub tex_coords: [f32; 2],
}

impl VoxelVertex {
    pub fn new(position: [f32; 3], normal: [f32; 3], color: [f32; 3]) -> Self {
        Self {
            position,
            normal,
            color,
            tex_coords: [0.0, 0.0], // Basic texture coordinates
        }
    }
    
    pub fn desc() -> wgpu::VertexBufferLayout<'static> {
        wgpu::VertexBufferLayout {
            array_stride: std::mem::size_of::<VoxelVertex>() as wgpu::BufferAddress,
            step_mode: wgpu::VertexStepMode::Vertex,
            attributes: &[
                wgpu::VertexAttribute {
                    offset: 0,
                    shader_location: 0,
                    format: wgpu::VertexFormat::Float32x3,
                },
                wgpu::VertexAttribute {
                    offset: std::mem::size_of::<[f32; 3]>() as wgpu::BufferAddress,
                    shader_location: 1,
                    format: wgpu::VertexFormat::Float32x3,
                },
                wgpu::VertexAttribute {
                    offset: std::mem::size_of::<[f32; 6]>() as wgpu::BufferAddress,
                    shader_location: 2,
                    format: wgpu::VertexFormat::Float32x3,
                },
                wgpu::VertexAttribute {
                    offset: std::mem::size_of::<[f32; 9]>() as wgpu::BufferAddress,
                    shader_location: 3,
                    format: wgpu::VertexFormat::Float32x2,
                },
            ],
        }
    }
}

/// Face direction for voxel cube faces
#[derive(Copy, Clone, Debug)]
enum FaceDirection {
    Front,
    Back,
    Left,
    Right,
    Top,
    Bottom,
}

impl FaceDirection {
    pub fn normal(&self) -> [f32; 3] {
        match self {
            FaceDirection::Front => [0.0, 0.0, 1.0],
            FaceDirection::Back => [0.0, 0.0, -1.0],
            FaceDirection::Left => [-1.0, 0.0, 0.0],
            FaceDirection::Right => [1.0, 0.0, 0.0],
            FaceDirection::Top => [0.0, 1.0, 0.0],
            FaceDirection::Bottom => [0.0, -1.0, 0.0],
        }
    }
    
    pub fn vertices(&self, pos: [f32; 3]) -> [[f32; 3]; 4] {
        let [x, y, z] = pos;
        
        match self {
            FaceDirection::Front => [
                [x, y, z + 1.0],
                [x + 1.0, y, z + 1.0],
                [x + 1.0, y + 1.0, z + 1.0],
                [x, y + 1.0, z + 1.0],
            ],
            FaceDirection::Back => [
                [x + 1.0, y, z],
                [x, y, z],
                [x, y + 1.0, z],
                [x + 1.0, y + 1.0, z],
            ],
            FaceDirection::Left => [
                [x, y, z],
                [x, y, z + 1.0],
                [x, y + 1.0, z + 1.0],
                [x, y + 1.0, z],
            ],
            FaceDirection::Right => [
                [x + 1.0, y, z + 1.0],
                [x + 1.0, y, z],
                [x + 1.0, y + 1.0, z],
                [x + 1.0, y + 1.0, z + 1.0],
            ],
            FaceDirection::Top => [
                [x, y + 1.0, z + 1.0],
                [x + 1.0, y + 1.0, z + 1.0],
                [x + 1.0, y + 1.0, z],
                [x, y + 1.0, z],
            ],
            FaceDirection::Bottom => [
                [x, y, z],
                [x + 1.0, y, z],
                [x + 1.0, y, z + 1.0],
                [x, y, z + 1.0],
            ],
        }
    }
}

/// High-performance mesh generator for voxel chunks
pub struct ChunkMeshGenerator;

impl ChunkMeshGenerator {
    /// Generate optimized mesh for a chunk using greedy meshing
    pub fn generate_mesh(chunk: &VoxelChunk, neighbors: &[Option<&VoxelChunk>; 6]) -> ChunkMesh {
        let mut mesh = ChunkMesh::new();
        
        // Use simple face culling for now (can be upgraded to greedy meshing)
        for x in 0..CHUNK_SIZE {
            for y in 0..CHUNK_SIZE {
                for z in 0..CHUNK_SIZE {
                    if let Some(voxel) = chunk.get_voxel(x, y, z) {
                        if voxel.is_solid() {
                            Self::add_voxel_faces(
                                &mut mesh,
                                chunk,
                                neighbors,
                                x, y, z,
                                voxel,
                            );
                        }
                    }
                }
            }
        }
        
        mesh
    }
    
    fn add_voxel_faces(
        mesh: &mut ChunkMesh,
        chunk: &VoxelChunk,
        neighbors: &[Option<&VoxelChunk>; 6],
        x: usize,
        y: usize,
        z: usize,
        voxel: &Voxel,
    ) {
        let world_pos = chunk.coord.to_world_pos();
        let voxel_pos = [
            world_pos.x + x as f32,
            world_pos.y + y as f32,
            world_pos.z + z as f32,
        ];
        
        let color = [
            voxel.color[0] as f32 / 255.0,
            voxel.color[1] as f32 / 255.0,
            voxel.color[2] as f32 / 255.0,
        ];
        
        // Check each face direction. At a chunk boundary, consult the
        // corresponding adjacent chunk rather than assuming air.
        let faces = [
            (FaceDirection::Front, (x, y, z as isize + 1)),
            (FaceDirection::Back, (x, y, z as isize - 1)),
            (FaceDirection::Left, (x as isize - 1, y, z as isize)),
            (FaceDirection::Right, (x as isize + 1, y, z as isize)),
            (FaceDirection::Top, (x, y as isize + 1, z as isize)),
            (FaceDirection::Bottom, (x, y as isize - 1, z as isize)),
        ];
        
        for (direction, neighbor_pos) in faces {
            if Self::should_render_face(chunk, neighbors, direction, neighbor_pos) {
                Self::add_face(mesh, direction, voxel_pos, color);
            }
        }
    }
    
    fn should_render_face(
        chunk: &VoxelChunk,
        neighbors: &[Option<&VoxelChunk>; 6],
        direction: FaceDirection,
        neighbor_pos: (isize, isize, isize),
    ) -> bool {
        let (nx, ny, nz) = neighbor_pos;
        if nx >= 0 && nx < CHUNK_SIZE as isize
            && ny >= 0 && ny < CHUNK_SIZE as isize
            && nz >= 0 && nz < CHUNK_SIZE as isize
        {
            return chunk
                .get_voxel(nx as usize, ny as usize, nz as usize)
                .map(|neighbor| !neighbor.is_solid())
                .unwrap_or(true);
        }

        // Neighbor ordering: front (+Z), back (-Z), left (-X), right (+X),
        // top (+Y), bottom (-Y). If the adjacent chunk is absent, render the
        // boundary face; an unloaded chunk is treated as open space.
        let index = match direction {
            FaceDirection::Front => 0,
            FaceDirection::Back => 1,
            FaceDirection::Left => 2,
            FaceDirection::Right => 3,
            FaceDirection::Top => 4,
            FaceDirection::Bottom => 5,
        };
        let Some(neighbor_chunk) = neighbors[index] else {
            return true;
        };

        let local = match direction {
            FaceDirection::Front => (nx, ny, 0),
            FaceDirection::Back => (nx, ny, CHUNK_SIZE as isize - 1),
            FaceDirection::Left => (CHUNK_SIZE as isize - 1, ny, nz),
            FaceDirection::Right => (0, ny, nz),
            FaceDirection::Top => (nx, 0, nz),
            FaceDirection::Bottom => (nx, CHUNK_SIZE as isize - 1, nz),
        };

        neighbor_chunk
            .get_voxel(local.0 as usize, local.1 as usize, local.2 as usize)
            .map(|neighbor| !neighbor.is_solid())
            .unwrap_or(true)
    }
    
    fn add_face(
        mesh: &mut ChunkMesh,
        direction: FaceDirection,
        pos: [f32; 3],
        color: [f32; 3],
    ) {
        let face_vertices = direction.vertices(pos);
        let normal = direction.normal();
        
        let start_index = mesh.vertices.len() as u32;
        
        // Add vertices
        for vertex_pos in face_vertices {
            mesh.vertices.push(VoxelVertex::new(vertex_pos, normal, color));
        }
        
        // Add indices (two triangles per face)
        mesh.indices.extend([
            start_index,
            start_index + 1,
            start_index + 2,
            start_index + 2,
            start_index + 3,
            start_index,
        ]);
    }
}

/// Main voxel world manager
pub struct VoxelWorld {
    pub chunks: HashMap<ChunkCoord, VoxelChunk>,
    pub loaded_chunks: std::collections::HashSet<ChunkCoord>,
    pub render_distance: i32,
    pub mesh_generator: ChunkMeshGenerator,
    
    // Performance tracking
    pub chunks_rendered: u32,
    pub triangles_rendered: u32,
}

impl VoxelWorld {
    pub fn new(render_distance: i32) -> Self {
        Self {
            chunks: HashMap::new(),
            loaded_chunks: std::collections::HashSet::new(),
            render_distance,
            mesh_generator: ChunkMeshGenerator,
            chunks_rendered: 0,
            triangles_rendered: 0,
        }
    }
    
    /// Load a chunk at the specified coordinates
    pub fn load_chunk(&mut self, coord: ChunkCoord) {
        if !self.loaded_chunks.contains(&coord) {
            let mut chunk = VoxelChunk::new(coord);
            
            // Generate some test content
            chunk.fill_test_pattern();
            
            self.chunks.insert(coord, chunk);
            self.loaded_chunks.insert(coord);
        }
    }
    
    /// Unload a chunk
    pub fn unload_chunk(&mut self, coord: ChunkCoord) {
        self.chunks.remove(&coord);
        self.loaded_chunks.remove(&coord);
    }
    
    /// Update chunks based on camera position
    pub fn update_chunks_around_camera(&mut self, camera_pos: Point3<f32>) {
        let center_chunk = ChunkCoord::from_world_pos(camera_pos);
        
        // Load chunks within render distance
        for x in (center_chunk.x - self.render_distance)..=(center_chunk.x + self.render_distance) {
            for y in (center_chunk.y - self.render_distance)..=(center_chunk.y + self.render_distance) {
                for z in (center_chunk.z - self.render_distance)..=(center_chunk.z + self.render_distance) {
                    let chunk_coord = ChunkCoord::new(x, y, z);
                    
                    // Simple distance check
                    let distance = ((x - center_chunk.x).abs() + 
                                  (y - center_chunk.y).abs() + 
                                  (z - center_chunk.z).abs());
                    
                    if distance <= self.render_distance {
                        self.load_chunk(chunk_coord);
                    }
                }
            }
        }
        
        // Unload chunks outside render distance
        let chunks_to_unload: Vec<ChunkCoord> = self.loaded_chunks
            .iter()
            .filter(|&&coord| {
                let distance = ((coord.x - center_chunk.x).abs() + 
                              (coord.y - center_chunk.y).abs() + 
                              (coord.z - center_chunk.z).abs());
                distance > self.render_distance + 1 // Add buffer zone
            })
            .copied()
            .collect();
        
        for coord in chunks_to_unload {
            self.unload_chunk(coord);
        }
    }
    
    /// Generate or update meshes for dirty chunks
    pub fn update_chunk_meshes(&mut self, device: &wgpu::Device) {
        self.chunks_rendered = 0;
        self.triangles_rendered = 0;
        
        // Build meshes from immutable chunk borrows first. This avoids the
        // Rust borrow conflict that would occur if we tried to read neighbors
        // while holding a mutable reference to the current chunk.
        let dirty_coords: Vec<ChunkCoord> = self.chunks
            .values()
            .filter(|chunk| chunk.dirty)
            .map(|chunk| chunk.coord)
            .collect();

        for coord in dirty_coords {
            let mesh = {
                let Some(chunk) = self.chunks.get(&coord) else { continue; };
                let neighbors = [
                    self.chunks.get(&ChunkCoord::new(coord.x, coord.y, coord.z + 1)),
                    self.chunks.get(&ChunkCoord::new(coord.x, coord.y, coord.z - 1)),
                    self.chunks.get(&ChunkCoord::new(coord.x - 1, coord.y, coord.z)),
                    self.chunks.get(&ChunkCoord::new(coord.x + 1, coord.y, coord.z)),
                    self.chunks.get(&ChunkCoord::new(coord.x, coord.y + 1, coord.z)),
                    self.chunks.get(&ChunkCoord::new(coord.x, coord.y - 1, coord.z)),
                ];
                ChunkMeshGenerator::generate_mesh(chunk, &neighbors)
            };

            let mut mesh = mesh;
            mesh.create_gpu_buffers(device);
            self.triangles_rendered += mesh.indices.len() as u32 / 3;

            if let Some(chunk) = self.chunks.get_mut(&coord) {
                chunk.mesh = Some(mesh);
                chunk.dirty = false;
            }
        }

        for chunk in self.chunks.values() {
            if chunk.mesh.is_some() {
                self.chunks_rendered += 1;
            }
        }
    }
    
    /// Get voxel at world position
    pub fn get_voxel_at_world_pos(&self, world_pos: Point3<f32>) -> Option<&Voxel> {
        let chunk_coord = ChunkCoord::from_world_pos(world_pos);
        let chunk = self.chunks.get(&chunk_coord)?;
        
        let local_x = (world_pos.x - chunk_coord.x as f32 * CHUNK_SIZE as f32).floor() as usize;
        let local_y = (world_pos.y - chunk_coord.y as f32 * CHUNK_SIZE as f32).floor() as usize;
        let local_z = (world_pos.z - chunk_coord.z as f32 * CHUNK_SIZE as f32).floor() as usize;
        
        chunk.get_voxel(local_x, local_y, local_z)
    }
    
    /// Set voxel at world position
    pub fn set_voxel_at_world_pos(&mut self, world_pos: Point3<f32>, voxel: Voxel) {
        let chunk_coord = ChunkCoord::from_world_pos(world_pos);
        
        // Load chunk if not present
        if !self.loaded_chunks.contains(&chunk_coord) {
            self.load_chunk(chunk_coord);
        }
        
        if let Some(chunk) = self.chunks.get_mut(&chunk_coord) {
            let local_x = (world_pos.x - chunk_coord.x as f32 * CHUNK_SIZE as f32).floor() as usize;
            let local_y = (world_pos.y - chunk_coord.y as f32 * CHUNK_SIZE as f32).floor() as usize;
            let local_z = (world_pos.z - chunk_coord.z as f32 * CHUNK_SIZE as f32).floor() as usize;
            
            chunk.set_voxel(local_x, local_y, local_z, voxel);

            // A boundary edit changes whether the adjacent chunk emits its
            // shared face, so invalidate that neighbor's mesh too.
            let neighbors = [
                (local_x == 0, ChunkCoord::new(chunk_coord.x - 1, chunk_coord.y, chunk_coord.z)),
                (local_x + 1 == CHUNK_SIZE, ChunkCoord::new(chunk_coord.x + 1, chunk_coord.y, chunk_coord.z)),
                (local_y == 0, ChunkCoord::new(chunk_coord.x, chunk_coord.y - 1, chunk_coord.z)),
                (local_y + 1 == CHUNK_SIZE, ChunkCoord::new(chunk_coord.x, chunk_coord.y + 1, chunk_coord.z)),
                (local_z == 0, ChunkCoord::new(chunk_coord.x, chunk_coord.y, chunk_coord.z - 1)),
                (local_z + 1 == CHUNK_SIZE, ChunkCoord::new(chunk_coord.x, chunk_coord.y, chunk_coord.z + 1)),
            ];
            for (touches_boundary, neighbor_coord) in neighbors {
                if touches_boundary {
                    if let Some(neighbor) = self.chunks.get_mut(&neighbor_coord) {
                        neighbor.dirty = true;
                    }
                }
            }
        }
    }
    
    pub fn get_loaded_chunks(&self) -> &HashMap<ChunkCoord, VoxelChunk> {
        &self.chunks
    }
    
    pub fn get_performance_stats(&self) -> (u32, u32) {
        (self.chunks_rendered, self.triangles_rendered)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_chunk_coordinates() {
        let coord = ChunkCoord::new(1, 2, 3);
        let world_pos = coord.to_world_pos();
        let back_to_coord = ChunkCoord::from_world_pos(world_pos);
        
        assert_eq!(coord, back_to_coord);
    }
    
    #[test]
    fn test_voxel_chunk() {
        let mut chunk = VoxelChunk::new(ChunkCoord::new(0, 0, 0));
        
        let test_voxel = Voxel::new(1, 255, [255, 0, 0]);
        chunk.set_voxel(0, 0, 0, test_voxel);
        
        let retrieved = chunk.get_voxel(0, 0, 0).unwrap();
        assert_eq!(retrieved.material_id, 1);
        assert_eq!(retrieved.density, 255);
        assert_eq!(retrieved.color, [255, 0, 0]);
    }
    
    #[test]
    fn test_coord_conversion() {
        let index = VoxelChunk::coord_to_index(5, 10, 15);
        let (x, y, z) = VoxelChunk::index_to_coord(index);
        
        assert_eq!((x, y, z), (5, 10, 15));
    }
    
    #[test]
    fn test_voxel_world() {
        let mut world = VoxelWorld::new(2);
        
        world.load_chunk(ChunkCoord::new(0, 0, 0));
        assert_eq!(world.loaded_chunks.len(), 1);
        
        world.unload_chunk(ChunkCoord::new(0, 0, 0));
        assert_eq!(world.loaded_chunks.len(), 0);
    }
}
