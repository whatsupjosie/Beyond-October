/*!
PubCast Complete Animation Controller

Main controller that orchestrates:
- Animation state machine with intelligent transitions  
- Avatar fitting and body morphing
- Hair simulation and physics
- Performance optimization and LOD
- Integration with skeleton system
- Real-time parameter control
*/

use super::avatar_animation_system::*;
use super::animation_data_library::*; 
use super::avatar_fitting_system::*;
use super::{JointTransform, SkeletalAnimator, SkeletonHierarchy};
use nalgebra::{Point3, UnitQuaternion, Vector3};
use std::collections::{HashMap, VecDeque};
use std::time::{Duration, Instant};

/// Main animation controller that manages all avatar animation systems
#[derive(Debug)]
pub struct CompleteAnimationController {
    // Core systems
    pub animation_controller: AnimationController,
    pub fitting_system: AvatarFittingSystem,
    pub state_machine: AdvancedStateMachine,
    
    // Runtime state
    pub current_time: f32,
    pub last_update: Instant,
    pub animation_speed: f32,
    
    // Performance management
    pub lod_manager: AnimationLODManager,
    pub update_scheduler: UpdateScheduler,
    pub parameter_cache: ParameterCache,
    
    // Event system
    pub event_handlers: HashMap<String, Box<dyn Fn(&AnimationEvent) + Send + Sync>>,
    pub pending_events: VecDeque<AnimationEvent>,
}

/// Advanced state machine with complex transition logic
#[derive(Debug, Clone)]
pub struct AdvancedStateMachine {
    pub states: HashMap<AnimationState, StateConfiguration>,
    pub transitions: Vec<StateTransition>,
    pub blend_trees: HashMap<String, BlendTreeNode>,
    pub parameters: HashMap<String, AnimationParameter>,
    pub condition_evaluator: ConditionEvaluator,
}

#[derive(Debug, Clone)]
pub struct StateConfiguration {
    pub state: AnimationState,
    pub can_interrupt: bool,
    pub minimum_play_time: f32,
    pub fade_in_time: f32,
    pub fade_out_time: f32,
    pub loop_count: Option<usize>,
    pub blend_mode: BlendMode,
}

#[derive(Debug, Clone)]
pub struct StateTransition {
    pub id: String,
    pub from_state: AnimationState,
    pub to_state: AnimationState,
    pub conditions: Vec<TransitionCondition>,
    pub transition_time: f32,
    pub priority: i32,
    pub interrupt_source: bool,
}

#[derive(Debug, Clone)]
pub enum BlendTreeNode {
    Animation {
        state: AnimationState,
        speed_multiplier: f32,
    },
    Blend2D {
        parameter_x: String,
        parameter_y: String,
        samples: Vec<BlendSample2D>,
    },
    AdditiveBlend {
        base: Box<BlendTreeNode>,
        additive: Box<BlendTreeNode>,
        weight_parameter: String,
    },
    LayeredBlend {
        layers: Vec<BlendLayer>,
    },
}

#[derive(Debug, Clone)]
pub struct BlendSample2D {
    pub position: (f32, f32),
    pub animation: AnimationState,
    pub threshold: f32,
}

#[derive(Debug, Clone)]
pub struct BlendLayer {
    pub node: Box<BlendTreeNode>,
    pub mask: Option<BoneMask>,
    pub weight_parameter: String,
    pub additive: bool,
}

#[derive(Debug, Clone)]
pub enum BlendMode {
    Replace,
    Additive,
    Multiply,
    Overlay { mask: BoneMask },
}

#[derive(Debug, Clone)]
pub struct AnimationParameter {
    pub name: String,
    pub value: ParameterValue,
    pub default_value: ParameterValue,
    pub interpolation_speed: f32,
    pub target_value: Option<ParameterValue>,
}

#[derive(Debug, Clone)]
pub enum ParameterValue {
    Float(f32),
    Int(i32),
    Bool(bool),
    Trigger(bool),
    Vector3(Vector3<f32>),
}

#[derive(Debug, Clone)]
pub struct ConditionEvaluator {
    pub custom_conditions: HashMap<String, Box<dyn Fn(&HashMap<String, ParameterValue>) -> bool + Send + Sync>>,
}

/// Level of Detail manager for animation performance
#[derive(Debug, Clone)]
pub struct AnimationLODManager {
    pub lod_levels: Vec<AnimationLOD>,
    pub distance_thresholds: Vec<f32>,
    pub importance_weights: HashMap<String, f32>,
    pub current_lod: usize,
}

#[derive(Debug, Clone)]
pub struct AnimationLOD {
    pub level: usize,
    pub bone_count_limit: usize,
    pub update_frequency: f32,
    pub hair_strand_limit: usize,
    pub enable_facial_animation: bool,
    pub enable_finger_animation: bool,
    pub enable_physics_simulation: bool,
}

/// Manages update scheduling for performance
#[derive(Debug, Clone)]
pub struct UpdateScheduler {
    pub frame_budget: Duration,
    pub update_queues: HashMap<UpdatePriority, VecDeque<UpdateTask>>,
    pub time_spent_this_frame: Duration,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum UpdatePriority {
    Critical,   // State machine, core animation
    High,       // Visible avatar animation
    Medium,     // Secondary animations, hair
    Low,        // Background avatars, idle effects
}

#[derive(Debug, Clone)]
pub struct UpdateTask {
    pub id: String,
    pub priority: UpdatePriority,
    pub estimated_cost: Duration,
    pub last_update: Instant,
    pub update_frequency: f32,
    pub task_type: TaskType,
}

#[derive(Debug, Clone)]
pub enum TaskType {
    AnimationBlending,
    PhysicsSimulation,
    ConstraintSolving,
    MorphTargetUpdate,
    HairSimulation,
    CollisionDetection,
}

/// Parameter caching for performance optimization
#[derive(Debug, Clone)]
pub struct ParameterCache {
    pub cached_values: HashMap<String, CachedValue>,
    pub dirty_flags: HashMap<String, bool>,
    pub dependency_graph: HashMap<String, Vec<String>>,
}

#[derive(Debug, Clone)]
pub struct CachedValue {
    pub value: ParameterValue,
    pub last_updated: Instant,
    pub expiry_time: Option<Instant>,
}

/// Animation events for callbacks and triggers
#[derive(Debug, Clone)]
pub enum AnimationEvent {
    StateChanged {
        from: AnimationState,
        to: AnimationState,
        transition_time: f32,
    },
    AnimationComplete {
        state: AnimationState,
        loop_count: usize,
    },
    ContactDetected {
        avatar_id: String,
        contact_joint: String,
        intensity: f32,
    },
    PhysicsEvent {
        event_type: PhysicsEventType,
        location: Point3<f32>,
        intensity: f32,
    },
    ParameterChanged {
        parameter_name: String,
        old_value: ParameterValue,
        new_value: ParameterValue,
    },
}

#[derive(Debug, Clone)]
pub enum PhysicsEventType {
    HairCollision,
    GroundContact,
    ObjectInteraction,
    WindGust,
}

impl CompleteAnimationController {
    pub fn new() -> Self {
        Self {
            animation_controller: AnimationController::new(),
            fitting_system: AvatarFittingSystem::new(),
            state_machine: AdvancedStateMachine::new(),
            current_time: 0.0,
            last_update: Instant::now(),
            animation_speed: 1.0,
            lod_manager: AnimationLODManager::new(),
            update_scheduler: UpdateScheduler::new(),
            parameter_cache: ParameterCache::new(),
            event_handlers: HashMap::new(),
            pending_events: VecDeque::new(),
        }
    }
    
    /// Initialize and fit an avatar to a skeleton with full animation support
    pub fn setup_avatar(
        &mut self,
        skeleton: &mut SkeletalAnimator,
        avatar_config: AvatarConfiguration,
    ) -> Result<String, String> {
        
        // Step 1: Fit avatar to skeleton
        let fitting_result = self.fitting_system
            .fit_avatar_to_skeleton(skeleton, &avatar_config)
            .map_err(|e| format!("Avatar fitting failed: {:?}", e))?;
        
        // Step 2: Configure animation controller for this avatar
        self.animation_controller.configure_avatar(avatar_config.clone());
        
        // Step 3: Setup performance LOD based on avatar complexity
        self.configure_lod_for_avatar(&avatar_config);
        
        // Step 4: Initialize state machine
        self.state_machine.reset_to_idle();
        
        // Step 5: Fire setup complete event
        self.pending_events.push_back(AnimationEvent::StateChanged {
            from: AnimationState::Idle { variant: IdleVariant::Basic },
            to: AnimationState::Idle { variant: IdleVariant::Basic },
            transition_time: 0.0,
        });
        
        Ok(format!("Avatar setup complete with profile: {}", fitting_result.applied_profile))
    }
    
    /// Main update loop - call this every frame
    pub fn update(&mut self, skeleton: &mut SkeletalAnimator, delta_time: f32) -> Result<(), String> {
        let start_time = Instant::now();
        
        // Update timing
        self.current_time += delta_time * self.animation_speed;
        let actual_delta = self.current_time - self.last_update.elapsed().as_secs_f32();
        self.last_update = start_time;
        
        // Process scheduled updates based on frame budget
        self.process_scheduled_updates(skeleton, actual_delta)?;
        
        // Process pending events
        self.process_events();
        
        // Update parameter cache
        self.parameter_cache.update();
        
        Ok(())
    }
    
    fn process_scheduled_updates(&mut self, skeleton: &mut SkeletalAnimator, delta_time: f32) -> Result<(), String> {
        self.update_scheduler.time_spent_this_frame = Duration::ZERO;
        
        // Process updates in priority order
        for priority in [UpdatePriority::Critical, UpdatePriority::High, UpdatePriority::Medium, UpdatePriority::Low] {
            if self.update_scheduler.time_spent_this_frame >= self.update_scheduler.frame_budget {
                break; // Out of time budget
            }
            
            self.process_priority_updates(skeleton, delta_time, priority)?;
        }
        
        Ok(())
    }
    
    fn process_priority_updates(
        &mut self,
        skeleton: &mut SkeletalAnimator,
        delta_time: f32,
        priority: UpdatePriority,
    ) -> Result<(), String> {
        
        if let Some(queue) = self.update_scheduler.update_queues.get_mut(&priority) {
            while let Some(task) = queue.pop_front() {
                if self.update_scheduler.time_spent_this_frame >= self.update_scheduler.frame_budget {
                    // Put task back and break
                    queue.push_front(task);
                    break;
                }
                
                let task_start = Instant::now();
                self.execute_update_task(skeleton, delta_time, &task)?;
                let task_duration = task_start.elapsed();
                
                self.update_scheduler.time_spent_this_frame += task_duration;
                
                // Re-schedule task if it's recurring
                if self.should_reschedule_task(&task) {
                    queue.push_back(task);
                }
            }
        }
        
        Ok(())
    }
    
    fn execute_update_task(
        &mut self,
        skeleton: &mut SkeletalAnimator,
        delta_time: f32,
        task: &UpdateTask,
    ) -> Result<(), String> {
        
        match task.task_type {
            TaskType::AnimationBlending => {
                self.update_animation_blending(skeleton, delta_time)?;
            },
            TaskType::PhysicsSimulation => {
                self.update_physics_simulation(skeleton, delta_time)?;
            },
            TaskType::ConstraintSolving => {
                self.update_constraints(skeleton, delta_time)?;
            },
            TaskType::MorphTargetUpdate => {
                self.update_morph_targets(skeleton, delta_time)?;
            },
            TaskType::HairSimulation => {
                self.update_hair_simulation(skeleton, delta_time)?;
            },
            TaskType::CollisionDetection => {
                self.update_collision_detection(skeleton, delta_time)?;
            },
        }
        
        Ok(())
    }
    
    fn update_animation_blending(&mut self, skeleton: &mut SkeletalAnimator, delta_time: f32) -> Result<(), String> {
        // Update state machine
        self.state_machine.update(delta_time, &mut self.parameter_cache)?;
        
        // Apply current animation state
        self.animation_controller.update(delta_time, skeleton);
        
        Ok(())
    }
    
    fn update_physics_simulation(&mut self, skeleton: &mut SkeletalAnimator, delta_time: f32) -> Result<(), String> {
        // Update avatar fitting system (includes physics)
        let avatar_config = &self.animation_controller.avatar_config.clone();
        self.fitting_system.update_avatar_fitting(skeleton, avatar_config, delta_time)
            .map_err(|e| format!("Physics simulation failed: {:?}", e))
    }
    
    // API Methods for external control
    
    /// Request a state change (e.g., from idle to walking)
    pub fn request_state_change(&mut self, new_state: AnimationState) -> Result<(), String> {
        // Check if transition is valid
        if self.state_machine.can_transition_to(&new_state) {
            self.animation_controller.request_state_change(new_state.clone());
            
            // Add to state machine transition queue
            self.state_machine.queue_transition(new_state);
            
            Ok(())
        } else {
            Err(format!("Invalid transition to state: {:?}", new_state))
        }
    }
    
    /// Set animation parameter (for blend trees and conditions)
    pub fn set_parameter(&mut self, name: &str, value: ParameterValue) -> Result<(), String> {
        let old_value = self.get_parameter(name).unwrap_or(ParameterValue::Float(0.0));
        
        // Update in animation controller
        match &value {
            ParameterValue::Float(v) => self.animation_controller.set_parameter(name, *v),
            _ => return Err("Only float parameters supported in basic controller".to_string()),
        }
        
        // Update in state machine
        self.state_machine.set_parameter(name, value.clone());
        
        // Update cache
        self.parameter_cache.set_parameter(name, value.clone());
        
        // Fire event
        self.pending_events.push_back(AnimationEvent::ParameterChanged {
            parameter_name: name.to_string(),
            old_value,
            new_value: value,
        });
        
        Ok(())
    }
    
    /// Get current animation parameter value
    pub fn get_parameter(&self, name: &str) -> Option<ParameterValue> {
        self.state_machine.parameters.get(name).map(|p| p.value.clone())
    }
    
    /// Configure body proportions (female curves, male bulk, etc.)
    pub fn set_body_proportions(&mut self, proportions: BodyProportions) -> Result<(), String> {
        self.animation_controller.avatar_config.body_proportions = proportions;
        
        // Mark morph targets as dirty for next update
        self.parameter_cache.mark_dirty("body_proportions");
        
        Ok(())
    }
    
    /// Configure hair settings with optional physics
    pub fn set_hair_configuration(&mut self, hair_config: HairConfiguration) -> Result<(), String> {
        self.animation_controller.avatar_config.hair_config = hair_config;
        
        // Schedule hair system update
        self.update_scheduler.schedule_task(UpdateTask {
            id: "hair_config_update".to_string(),
            priority: UpdatePriority::Medium,
            estimated_cost: Duration::from_millis(5),
            last_update: Instant::now(),
            update_frequency: 0.0, // One-time update
            task_type: TaskType::HairSimulation,
        });
        
        Ok(())
    }
    
    /// Enable/disable hair physics simulation
    pub fn set_hair_physics_enabled(&mut self, enabled: bool) -> Result<(), String> {
        self.animation_controller.avatar_config.hair_config.simulation_enabled = enabled;
        Ok(())
    }
    
    /// Set animation playback speed (1.0 = normal, 0.5 = half speed, 2.0 = double speed)
    pub fn set_animation_speed(&mut self, speed: f32) {
        self.animation_speed = speed.max(0.0);
    }
    
    /// Get current animation state
    pub fn get_current_state(&self) -> &AnimationState {
        &self.animation_controller.current_state
    }
    
    /// Get target animation state (if transitioning)
    pub fn get_target_state(&self) -> &AnimationState {
        &self.animation_controller.target_state
    }
    
    /// Get transition progress (0.0 to 1.0)
    pub fn get_transition_progress(&self) -> f32 {
        self.animation_controller.transition_progress
    }
    
    /// Check if currently transitioning between states
    pub fn is_transitioning(&self) -> bool {
        self.animation_controller.current_state != self.animation_controller.target_state
    }
    
    // Convenience methods for common actions
    
    /// Start walking forward
    pub fn start_walking(&mut self, gender_variant: GenderVariant) -> Result<(), String> {
        self.request_state_change(AnimationState::Walking {
            direction: WalkDirection::Forward,
            gender_variant,
        })
    }
    
    /// Start running forward
    pub fn start_running(&mut self) -> Result<(), String> {
        self.request_state_change(AnimationState::Running {
            direction: RunDirection::Forward,
        })
    }
    
    /// Start high heel walk (female avatars)
    pub fn start_high_heel_walk(&mut self, hip_emphasis: f32) -> Result<(), String> {
        self.request_state_change(AnimationState::HighHeelWalk {
            speed: WalkSpeed::Normal,
            hip_emphasis: hip_emphasis.clamp(0.0, 1.0),
        })
    }
    
    /// Return to idle state
    pub fn return_to_idle(&mut self, idle_variant: Option<IdleVariant>) -> Result<(), String> {
        let variant = idle_variant.unwrap_or(IdleVariant::Basic);
        self.request_state_change(AnimationState::Idle { variant })
    }
    
    /// Perform a jump
    pub fn jump(&mut self) -> Result<(), String> {
        self.request_state_change(AnimationState::Jumping {
            phase: JumpPhase::Crouch,
        })
    }
    
    /// Sit down in a chair
    pub fn sit_in_chair(&mut self) -> Result<(), String> {
        self.request_state_change(AnimationState::Sitting {
            furniture_type: SittingType::Chair,
        })
    }
    
    /// Start typing at computer
    pub fn start_typing(&mut self, intensity: TypingIntensity) -> Result<(), String> {
        self.request_state_change(AnimationState::Typing {
            surface_type: TypingType::Computer,
            intensity,
        })
    }
    
    /// Perform handshake
    pub fn handshake(&mut self, hand: HandType) -> Result<(), String> {
        self.request_state_change(AnimationState::Handshaking {
            hand,
            progress: 0.0,
        })
    }
    
    /// Perform bow gesture
    pub fn bow(&mut self, depth: BowDepth, formality: FormalityLevel) -> Result<(), String> {
        self.request_state_change(AnimationState::Bowing {
            depth,
            formality,
        })
    }
    
    /// Perform curtsey gesture (female avatars)
    pub fn curtsey(&mut self, depth: CurtsyDepth, elegance: EleganceLevel) -> Result<(), String> {
        self.request_state_change(AnimationState::Curtseying {
            depth,
            elegance,
        })
    }
    
    /// Apply lipstick (female avatars)
    pub fn apply_lipstick(&mut self) -> Result<(), String> {
        self.request_state_change(AnimationState::MakeupAction {
            action: MakeupActionType::Lipstick,
            progress: 0.0,
        })
    }
    
    /// Open purse (female avatars)
    pub fn open_purse(&mut self) -> Result<(), String> {
        self.request_state_change(AnimationState::PurseAction {
            action: PurseActionType::Opening,
            progress: 0.0,
        })
    }
    
    // Event system
    
    /// Add event handler for animation events
    pub fn add_event_handler<F>(&mut self, event_type: &str, handler: F)
    where
        F: Fn(&AnimationEvent) + Send + Sync + 'static,
    {
        self.event_handlers.insert(event_type.to_string(), Box::new(handler));
    }
    
    fn process_events(&mut self) {
        while let Some(event) = self.pending_events.pop_front() {
            // Call registered handlers
            for (event_type, handler) in &self.event_handlers {
                if self.event_matches_type(&event, event_type) {
                    handler(&event);
                }
            }
        }
    }
    
    fn event_matches_type(&self, event: &AnimationEvent, event_type: &str) -> bool {
        match event {
            AnimationEvent::StateChanged { .. } => event_type == "state_changed",
            AnimationEvent::AnimationComplete { .. } => event_type == "animation_complete",
            AnimationEvent::ContactDetected { .. } => event_type == "contact_detected",
            AnimationEvent::PhysicsEvent { .. } => event_type == "physics_event",
            AnimationEvent::ParameterChanged { .. } => event_type == "parameter_changed",
        }
    }
    
    // Performance and configuration
    
    fn configure_lod_for_avatar(&mut self, avatar_config: &AvatarConfiguration) {
        // Adjust LOD based on avatar complexity
        let hair_complexity = if avatar_config.hair_config.simulation_enabled { 2 } else { 0 };
        let body_complexity = match avatar_config.gender {
            Gender::Female => 1, // Additional morphing complexity
            Gender::Male => 1,
            _ => 0,
        };
        
        let total_complexity = hair_complexity + body_complexity;
        
        // Adjust thresholds based on complexity
        self.lod_manager.distance_thresholds = match total_complexity {
            0..=1 => vec![10.0, 25.0, 50.0], // Simple avatar
            2..=3 => vec![8.0, 20.0, 40.0],  // Medium complexity
            _ => vec![5.0, 15.0, 30.0],      // High complexity
        };
    }
    
    /// Set performance level (0 = highest quality, 3 = lowest quality/best performance)
    pub fn set_performance_level(&mut self, level: usize) -> Result<(), String> {
        if level >= self.lod_manager.lod_levels.len() {
            return Err("Invalid performance level".to_string());
        }
        
        self.lod_manager.current_lod = level;
        
        // Update frame budget based on performance level
        self.update_scheduler.frame_budget = match level {
            0 => Duration::from_millis(16), // 60 FPS budget
            1 => Duration::from_millis(20), // 50 FPS budget  
            2 => Duration::from_millis(33), // 30 FPS budget
            _ => Duration::from_millis(50), // 20 FPS budget
        };
        
        Ok(())
    }
    
    // Stub implementations for complex update methods
    fn update_constraints(&mut self, _skeleton: &mut SkeletalAnimator, _delta_time: f32) -> Result<(), String> { Ok(()) }
    fn update_morph_targets(&mut self, _skeleton: &mut SkeletalAnimator, _delta_time: f32) -> Result<(), String> { Ok(()) }
    fn update_hair_simulation(&mut self, _skeleton: &mut SkeletalAnimator, _delta_time: f32) -> Result<(), String> { Ok(()) }
    fn update_collision_detection(&mut self, _skeleton: &mut SkeletalAnimator, _delta_time: f32) -> Result<(), String> { Ok(()) }
    fn should_reschedule_task(&self, _task: &UpdateTask) -> bool { false }
}

// Implementation of helper systems
impl AdvancedStateMachine {
    pub fn new() -> Self {
        Self {
            states: HashMap::new(),
            transitions: Vec::new(),
            blend_trees: HashMap::new(),
            parameters: HashMap::new(),
            condition_evaluator: ConditionEvaluator::new(),
        }
    }
    
    pub fn reset_to_idle(&mut self) {
        // Implementation would reset to idle state
    }
    
    pub fn can_transition_to(&self, _state: &AnimationState) -> bool {
        true // Simplified - real implementation would check transition rules
    }
    
    pub fn queue_transition(&mut self, _state: AnimationState) {
        // Implementation would queue transition
    }
    
    pub fn set_parameter(&mut self, name: &str, value: ParameterValue) {
        if let Some(param) = self.parameters.get_mut(name) {
            param.value = value;
        } else {
            self.parameters.insert(name.to_string(), AnimationParameter {
                name: name.to_string(),
                value: value.clone(),
                default_value: value,
                interpolation_speed: 1.0,
                target_value: None,
            });
        }
    }
    
    pub fn update(&mut self, _delta_time: f32, _cache: &mut ParameterCache) -> Result<(), String> {
        // Implementation would update state machine logic
        Ok(())
    }
}

impl ConditionEvaluator {
    pub fn new() -> Self {
        Self {
            custom_conditions: HashMap::new(),
        }
    }
}

impl AnimationLODManager {
    pub fn new() -> Self {
        Self {
            lod_levels: vec![
                AnimationLOD { // Level 0 - Highest quality
                    level: 0,
                    bone_count_limit: 100,
                    update_frequency: 60.0,
                    hair_strand_limit: 200,
                    enable_facial_animation: true,
                    enable_finger_animation: true,
                    enable_physics_simulation: true,
                },
                AnimationLOD { // Level 1 - High quality  
                    level: 1,
                    bone_count_limit: 50,
                    update_frequency: 30.0,
                    hair_strand_limit: 100,
                    enable_facial_animation: true,
                    enable_finger_animation: false,
                    enable_physics_simulation: true,
                },
                AnimationLOD { // Level 2 - Medium quality
                    level: 2,
                    bone_count_limit: 25,
                    update_frequency: 20.0,
                    hair_strand_limit: 50,
                    enable_facial_animation: false,
                    enable_finger_animation: false,
                    enable_physics_simulation: false,
                },
                AnimationLOD { // Level 3 - Lowest quality/Best performance
                    level: 3,
                    bone_count_limit: 15,
                    update_frequency: 10.0,
                    hair_strand_limit: 0,
                    enable_facial_animation: false,
                    enable_finger_animation: false,
                    enable_physics_simulation: false,
                },
            ],
            distance_thresholds: vec![10.0, 25.0, 50.0],
            importance_weights: HashMap::new(),
            current_lod: 0,
        }
    }
}

impl UpdateScheduler {
    pub fn new() -> Self {
        let mut update_queues = HashMap::new();
        update_queues.insert(UpdatePriority::Critical, VecDeque::new());
        update_queues.insert(UpdatePriority::High, VecDeque::new());
        update_queues.insert(UpdatePriority::Medium, VecDeque::new());
        update_queues.insert(UpdatePriority::Low, VecDeque::new());
        
        Self {
            frame_budget: Duration::from_millis(16), // 60 FPS default
            update_queues,
            time_spent_this_frame: Duration::ZERO,
        }
    }
    
    pub fn schedule_task(&mut self, task: UpdateTask) {
        if let Some(queue) = self.update_queues.get_mut(&task.priority) {
            queue.push_back(task);
        }
    }
}

impl ParameterCache {
    pub fn new() -> Self {
        Self {
            cached_values: HashMap::new(),
            dirty_flags: HashMap::new(),
            dependency_graph: HashMap::new(),
        }
    }
    
    pub fn set_parameter(&mut self, name: &str, value: ParameterValue) {
        self.cached_values.insert(name.to_string(), CachedValue {
            value,
            last_updated: Instant::now(),
            expiry_time: None,
        });
        self.mark_dirty(name);
    }
    
    pub fn mark_dirty(&mut self, name: &str) {
        self.dirty_flags.insert(name.to_string(), true);
    }
    
    pub fn update(&mut self) {
        // Implementation would update cached values and dependencies
        self.dirty_flags.clear();
    }
}
