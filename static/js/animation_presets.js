// Avatar Animation Presets - Walk, Sit, Wave, Type
//
// This file defines a handful of simple animation tracks for use with
// PubCast avatars. Each preset contains the duration, loop flag and a
// set of per‑bone tracks. Tracks define keyframes for either position
// or rotation. These definitions are designed to be consumed by an
// animation system that can interpolate between keyframes over time.
//
// Note: These animations are not currently consumed by the default
// stage renderer (which uses simple breathing and sway). They are
// provided here for future expansion and integration with a full
// skeletal system or the HolographicAvatar class in avatar_glow.js.

export const ANIMATION_PRESETS = {
  walk: {
    duration: 2.0,
    loop: true,
    tracks: {
      root: { position: [{time:0,value:[0,0,0]},{time:2,value:[0,0,-2]}] },
      thigh_l: { rotation: [{time:0,value:[0.4,0,0]},{time:1,value:[-0.4,0,0]},{time:2,value:[0.4,0,0]}] },
      thigh_r: { rotation: [{time:0,value:[-0.4,0,0]},{time:1,value:[0.4,0,0]},{time:2,value:[-0.4,0,0]}] },
      upperarm_l: { rotation: [{time:0,value:[-0.3,0,0]},{time:1,value:[0.3,0,0]},{time:2,value:[-0.3,0,0]}] },
      upperarm_r: { rotation: [{time:0,value:[0.3,0,0]},{time:1,value:[-0.3,0,0]},{time:2,value:[0.3,0,0]}] }
    }
  },
  sit: {
    duration: 3.0,
    loop: false,
    tracks: {
      root: { position: [{time:0,value:[0,0,0]},{time:3,value:[0,-0.6,0]}] },
      thigh_l: { rotation: [{time:0,value:[0,0,0]},{time:3,value:[1.57,0,0]}] },
      thigh_r: { rotation: [{time:0,value:[0,0,0]},{time:3,value:[1.57,0,0]}] },
      calf_l: { rotation: [{time:0,value:[0,0,0]},{time:3,value:[-1.57,0,0]}] },
      calf_r: { rotation: [{time:0,value:[0,0,0]},{time:3,value:[-1.57,0,0]}] }
    }
  },
  wave: {
    duration: 2.0,
    loop: false,
    tracks: {
      upperarm_r: { rotation: [{time:0,value:[0,0,0]},{time:0.5,value:[0,0,-1.57]}] },
      lowerarm_r: { rotation: [{time:0.5,value:[0,0,0]},{time:0.7,value:[0,0.6,0]},{time:0.9,value:[0,-0.6,0]},{time:1.1,value:[0,0.6,0]}] }
    }
  },
  type: {
    duration: 4.0,
    loop: true,
    tracks: {
      root: { position: [{time:0,value:[0,-0.6,0]}] },
      upperarm_l: { rotation: [{time:0,value:[-0.5,0,0.3]}] },
      upperarm_r: { rotation: [{time:0,value:[-0.5,0,-0.3]}] },
      lowerarm_l: { rotation: [{time:0,value:[-0.8,0,0]}] },
      lowerarm_r: { rotation: [{time:0,value:[-0.8,0,0]}] }
    }
  },
  idle: {
    duration: 4.0,
    loop: true,
    tracks: {
      chest: { rotation: [{time:0,value:[0,0,0]},{time:2,value:[0.03,0,0]},{time:4,value:[0,0,0]}] }
    }
  }
};