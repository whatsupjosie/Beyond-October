use pubcast_camera::demo::bootstrap::{demo_control_room,demo_scene};
fn main() {
    let (engine, mut adapter)=demo_control_room();
    let scene=demo_scene();
    if let Some((packet, stats))=adapter.frame(&engine,Some("pub_demo".into()),&scene) {
        println!("camera={} visible={} rendered={}",packet.camera_id,packet.visible_object_ids.len(),stats.rendered);
    } else { eprintln!("No active camera"); std::process::exit(1); }
}
