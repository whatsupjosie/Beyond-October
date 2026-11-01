# PubCast deferred feature: Performance and protected background tasks
Date: 2026-10-21
Status: Requested; deliberately deferred. Do not implement during current Counter stabilization work.

## Standing project-status reminder
Whenever reviewing "where are we at?" or "what have we got to do?", include this feature in the deferred backlog. Keep it distinct from implemented functionality and current blockers. Bring it forward for prioritization without silently starting it.

## User intent
Settings > Performance controls how much runs simultaneously and which PubCast activities may continue in the background. Inactive programs retain essential saving/state preservation while optional playback, animation, polling and automatic checks can pause. Task assignment can explicitly authorize background execution until completion, with a visible activity/progress indicator and completion notification.

Protected activities include downloads, uploads, installations, rendering, integration, recording and explicitly authorized AI work. Before applying a setting that would disrupt them, list the actual affected tasks and let the user decide individually: finish, pause/checkpoint where supported, safely cancel, or open the task to wrap it up. Apply only after those decisions. Finish grants a task-specific exception that expires at completion. Closing a window is distinct from cancelling its task. Do not offer pause/resume or rollback unless supported by that operation; commit phases must reach a safe stopping point.

Provide task visibility, progress, resource contention explanation, and appropriate pause, end, save and revisit controls. Preserve essential saves when restricting background work.

A durable outgoing queue can hold explicitly authorized uploads to a specified GitHub repository, Google Drive/Docs destination, or email recipient. Retain the intended saved version, destination and connection policy. Support waiting for a user-approved connection suitable for file size, avoiding phone/metered internet as requested. Survive restart, retry safely and prevent duplicate deliveries. Scheduling a queued action does not grant unrelated recipient or destination permissions.

Optional OS integration should use supported, explicit controls for nonessential background work without disabling security. PubCast cannot assume universal control over unrelated applications or updaters. Investigate platform support separately.

## Engineering acceptance criteria for later
- Discover and reuse existing task/job, persistence, settings and transfer mechanisms before adding new ones.
- Central task lifecycle independent of window focus; program adapters enforce policies.
- Warning enumerates real affected tasks and supported decisions; revalidate if tasks change before applying.
- Protected work is not interrupted silently; task exceptions expire on completion.
- Checkpoint/restart, cancellation, failure recovery and transfer deduplication are tested.
- Verify with real workloads and existing audio/rendering workflows.
- This feature reduces workload contention; it does not replace fixing expensive tray physics.

## Scope and estimate
A settings mockup is not a working scheduler. No claim that the full feature can be built and verified in 5–10 minutes. Estimate after inventorying existing task infrastructure and adapters; OS integration and outgoing transfers are separate stages.

## Current priority
Continue Counter stabilization, performance investigation and real-workflow verification. No runtime implementation authorized by this note; the user explicitly requested deferral.


## Asset-preview clarification, also deferred

The user expects FBX/OBJ/GLB asset preview, compatible embedded or separately loaded animations, and 2D/3D/parallax viewing choices. This is an asset viewer, not Blender or a complete scene editor. Animation compatibility/retargeting must be explicit. The user clarified this was a related question and explicitly directed continuation of the current file-workspace work. Do not switch to building the viewer without prioritizing it separately.
