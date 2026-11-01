// Voxel Shader for PubCast AI Renderer
// High-performance WGSL shader for real-time voxel rendering with lighting and shadows

struct CameraUniform {
    view_proj: mat4x4<f32>,
}

struct VertexInput {
    @location(0) position: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) color: vec3<f32>,
    @location(3) tex_coords: vec2<f32>,
}

struct VertexOutput {
    @builtin(position) clip_position: vec4<f32>,
    @location(0) world_position: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) color: vec3<f32>,
    @location(3) tex_coords: vec2<f32>,
}

struct FragmentOutput {
    @location(0) color: vec4<f32>,
}

@group(0) @binding(0)
var<uniform> camera: CameraUniform;

// Lighting constants
const AMBIENT_LIGHT: vec3<f32> = vec3<f32>(0.2, 0.3, 0.4);
const AMBIENT_INTENSITY: f32 = 0.3;
const SUN_DIRECTION: vec3<f32> = vec3<f32>(-0.5, -1.0, -0.3);
const SUN_COLOR: vec3<f32> = vec3<f32>(1.0, 0.9, 0.8);
const SUN_INTENSITY: f32 = 1.0;

@vertex
fn vs_main(model: VertexInput) -> VertexOutput {
    var out: VertexOutput;
    
    // Transform position to clip space
    out.clip_position = camera.view_proj * vec4<f32>(model.position, 1.0);
    
    // Pass world position for lighting calculations
    out.world_position = model.position;
    
    // Transform normal (assuming no non-uniform scaling for now)
    out.normal = normalize(model.normal);
    
    // Pass through color and texture coordinates
    out.color = model.color;
    out.tex_coords = model.tex_coords;
    
    return out;
}

@fragment
fn fs_main(in: VertexOutput) -> FragmentOutput {
    var out: FragmentOutput;
    
    // Normalize the normal vector
    let normal = normalize(in.normal);
    
    // Calculate ambient lighting
    let ambient = AMBIENT_LIGHT * AMBIENT_INTENSITY;
    
    // Calculate directional lighting (sun)
    let sun_dir = normalize(-SUN_DIRECTION);
    let diffuse_strength = max(dot(normal, sun_dir), 0.0);
    let diffuse = SUN_COLOR * SUN_INTENSITY * diffuse_strength;
    
    // Simple Blinn-Phong specular highlight
    let view_dir = normalize(-in.world_position); // Assuming camera at origin for now
    let halfway_dir = normalize(sun_dir + view_dir);
    let specular_strength = pow(max(dot(normal, halfway_dir), 0.0), 64.0);
    let specular = SUN_COLOR * specular_strength * 0.3;
    
    // Combine lighting with voxel color
    let lighting = ambient + diffuse + specular;
    let final_color = in.color * lighting;
    
    // Add some atmospheric fog based on distance
    let distance = length(in.world_position);
    let fog_factor = 1.0 - exp(-distance * 0.01);
    let fog_color = vec3<f32>(0.7, 0.8, 0.9);
    let final_with_fog = mix(final_color, fog_color, fog_factor * 0.3);
    
    out.color = vec4<f32>(final_with_fog, 1.0);
    
    return out;
}

// Alternative simplified shader for high-performance mode
@vertex
fn vs_simple(model: VertexInput) -> VertexOutput {
    var out: VertexOutput;
    
    out.clip_position = camera.view_proj * vec4<f32>(model.position, 1.0);
    out.world_position = model.position;
    out.normal = model.normal;
    out.color = model.color;
    out.tex_coords = model.tex_coords;
    
    return out;
}

@fragment
fn fs_simple(in: VertexOutput) -> FragmentOutput {
    var out: FragmentOutput;
    
    // Simple lighting without specular
    let normal = normalize(in.normal);
    let sun_dir = normalize(-SUN_DIRECTION);
    let diffuse_strength = max(dot(normal, sun_dir), 0.0);
    
    let lighting = AMBIENT_LIGHT * AMBIENT_INTENSITY + SUN_COLOR * diffuse_strength * 0.7;
    let final_color = in.color * lighting;
    
    out.color = vec4<f32>(final_color, 1.0);
    
    return out;
}
