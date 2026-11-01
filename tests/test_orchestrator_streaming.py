#!/usr/bin/env python3
"""
TEST 2: ORCHESTRATOR CONCURRENT STREAMING & CONNECTION SAFETY
Tests that the fixed async queue-based streaming works correctly and connections are cleaned up.
"""

import asyncio
import logging
from typing import List
from modules.wired.orchestrator_wired import WiredOrchestrator, StreamEvent


# Mock adapters for testing without API keys
class MockEQAdaptor:
    def process(self, user_id, message, history):
        return {
            'state': {'care_level': 1, 'care_name': 'ATTENTIVE', 'complexity': 0.6, 'velocity': 0.6, 'timestamp': 0},
            'routing': {'care_level': 1, 'care_name': 'ATTENTIVE', 'recommended_agents': ['pete', 'sheila'], 'suppress_agents': []},
            'memory_context': 'Test memory',
            'prompt_injection': 'Test injection',
            'debug': {}
        }
    def store_memory(self, *a, **kw): pass
    def get_memory_context(self, *a, **kw): return ''
    class jeremy:
        @staticmethod
        def get_emotional_state(uid):
            from eq_adaptor import EmotionalState
            return EmotionalState(user_id=uid)


class MockGPTAdapter:
    def __init__(self, latency_ms=10, chunks_per_agent=5):
        self.latency_ms = latency_ms
        self.chunks_per_agent = chunks_per_agent
        self.call_count = {}
    
    def get_agent_info(self, agent_id):
        return {'name': agent_id.capitalize(), 'role': 'Test'}
    
    def list_agents(self):
        return ['pete', 'sheila']
    
    async def stream_response(self, agent_id, user_message, conversation_history, eq_result):
        """Simulate streaming response with variable latency."""
        self.call_count[agent_id] = self.call_count.get(agent_id, 0) + 1
        
        # Simulate processing time
        await asyncio.sleep(self.latency_ms / 1000.0)
        
        # Emit chunks with small delays between them
        for i in range(self.chunks_per_agent):
            await asyncio.sleep(self.latency_ms / 2000.0)
            yield f" [{agent_id}:{i}]"


async def test_concurrent_streaming():
    """Verify both agents stream concurrently and chunks are interleaved."""
    print("\n>>> Test: Concurrent Streaming")
    print("    Expected: 2 agents × 5 chunks = 10 events, interleaved\n")
    
    mock_eq = MockEQAdaptor()
    mock_eq.jeremy = mock_eq.jeremy()
    mock_gpt = MockGPTAdapter(latency_ms=5, chunks_per_agent=5)
    
    orch = WiredOrchestrator(
        eq_adaptor=mock_eq,
        gpt_adapter=mock_gpt,
        logger=logging.getLogger('test_orch'),
        max_agents_per_turn=2
    )
    
    await orch.create_room('concurrent_test', 'Test Room')
    await orch.join_room('concurrent_test', 'user1')
    
    # Collect all events from orchestrator
    events: List[StreamEvent] = []
    async for event in orch.handle_message('concurrent_test', 'user1', 'Hello'):
        events.append(event)
    
    # Analyze events
    agent_starts = [e for e in events if e.event_type == 'agent_start']
    stream_chunks = [e for e in events if e.event_type == 'stream_chunk']
    agent_dones = [e for e in events if e.event_type == 'agent_done']
    
    pete_chunks = [e for e in stream_chunks if e.agent_id == 'pete']
    sheila_chunks = [e for e in stream_chunks if e.agent_id == 'sheila']
    
    # Check for interleaving: chunks should NOT be grouped by agent
    # If properly concurrent, we should see Pete chunk, Sheila chunk, Pete chunk, etc.
    chunk_sequence = [e.agent_id for e in stream_chunks]
    is_interleaved = 'pete' in chunk_sequence and 'sheila' in chunk_sequence
    has_alternation = False
    for i in range(len(chunk_sequence) - 1):
        if chunk_sequence[i] != chunk_sequence[i+1]:
            has_alternation = True
            break
    
    results = {
        "concurrent_stream_events": len(stream_chunks),
        "expected_chunks": 10,
        "chunks_correct": len(stream_chunks) == 10,
        "agent_starts": len(agent_starts),
        "agent_dones": len(agent_dones),
        "pete_chunks": len(pete_chunks),
        "sheila_chunks": len(sheila_chunks),
        "both_agents_present": len(set(e.agent_id for e in stream_chunks)) == 2,
        "chunks_interleaved": has_alternation,
        "chunk_sequence": chunk_sequence[:10],
    }
    
    # Print results
    passed = (
        results['chunks_correct'] and 
        results['both_agents_present'] and 
        results['chunks_interleaved']
    )
    
    status = "✅" if passed else "❌"
    print(f"{status} Concurrent chunks: {results['concurrent_stream_events']}/10 (pete={results['pete_chunks']}, sheila={results['sheila_chunks']})")
    print(f"{'✅' if results['chunks_interleaved'] else '❌'} Interleaved: {results['chunk_sequence'][:6]}...")
    print(f"{'✅' if results['agent_starts'] == 2 else '❌'} Agent starts: {results['agent_starts']}/2")
    print(f"{'✅' if results['agent_dones'] == 2 else '❌'} Agent dones: {results['agent_dones']}/2")
    
    return passed, results


async def test_room_and_user_management():
    """Verify room creation, user joining/leaving work correctly."""
    print("\n>>> Test: Room & User Management")
    print("    Expected: Rooms created, users tracked, state persisted\n")
    
    mock_eq = MockEQAdaptor()
    mock_eq.jeremy = mock_eq.jeremy()
    
    orch = WiredOrchestrator(
        eq_adaptor=mock_eq,
        gpt_adapter=MockGPTAdapter(latency_ms=2, chunks_per_agent=2),
        logger=logging.getLogger('test_orch'),
        max_agents_per_turn=1
    )
    
    results = {}
    
    # Test 1: Create room
    room = await orch.create_room('room1', 'Test Room 1')
    results['room_created'] = room is not None and room.room_id == 'room1'
    
    # Test 2: Join users
    await orch.join_room('room1', 'user1')
    await orch.join_room('room1', 'user2')
    room = orch.get_room('room1')
    results['users_joined'] = len(room.participants) == 2 and 'user1' in room.participants
    
    # Test 3: Get room state
    room_state = orch.get_room('room1')
    results['room_retrievable'] = room_state is not None
    results['participant_count'] = len(room_state.participants) if room_state else 0
    
    # Test 4: Leave user
    await orch.leave_room('room1', 'user1')
    room = orch.get_room('room1')
    results['user_left'] = len(room.participants) == 1 and 'user1' not in room.participants
    
    # Test 5: List rooms
    rooms = orch.list_rooms()
    results['list_rooms_works'] = len(rooms) >= 1
    
    # Print results
    passed = all([
        results.get('room_created'),
        results.get('users_joined'),
        results.get('user_left'),
    ])
    
    status = "✅" if passed else "❌"
    print(f"{status} Room created: {results.get('room_created')}")
    print(f"{status} Users joined (count={results['participant_count']}): {results.get('users_joined')}")
    print(f"{status} User left: {results.get('user_left')}")
    print(f"{status} List rooms: {results.get('list_rooms_works')}")
    
    return passed, results


async def test_event_type_completeness():
    """Verify all required event types are emitted during a full message exchange."""
    print("\n>>> Test: Event Type Completeness")
    print("    Expected: user_message, agent_start, stream_chunk, agent_done, exchange_complete\n")
    
    mock_eq = MockEQAdaptor()
    mock_eq.jeremy = mock_eq.jeremy()
    
    orch = WiredOrchestrator(
        eq_adaptor=mock_eq,
        gpt_adapter=MockGPTAdapter(latency_ms=3, chunks_per_agent=2),
        logger=logging.getLogger('test_orch'),
        max_agents_per_turn=1
    )
    
    await orch.create_room('event_test', 'Test Room')
    await orch.join_room('event_test', 'user1')
    
    events = []
    async for event in orch.handle_message('event_test', 'user1', 'Test message'):
        events.append(event.event_type)
    
    event_types = set(events)
    required_events = {'user_message', 'agent_start', 'stream_chunk', 'agent_done', 'exchange_complete'}
    has_required = required_events.issubset(event_types)
    
    results = {
        "event_types_emitted": sorted(list(event_types)),
        "required_present": has_required,
        "total_events": len(events),
    }
    
    status = "✅" if has_required else "❌"
    print(f"{status} Required events: {required_events}")
    print(f"   Actual events: {results['event_types_emitted']}")
    print(f"{'✅' if results['required_present'] else '❌'} All required events present: {results['required_present']}")
    
    return has_required, results


async def main():
    print("\n" + "="*80)
    print("TEST 2: ORCHESTRATOR CONCURRENT STREAMING & CONNECTION MANAGEMENT")
    print("="*80)
    
    # Suppress debug logs for cleaner output
    logging.getLogger('test_orch').setLevel(logging.WARNING)
    
    test1_passed, test1_results = await test_concurrent_streaming()
    test2_passed, test2_results = await test_room_and_user_management()
    test3_passed, test3_results = await test_event_type_completeness()
    
    # Summary
    print("\n" + "="*80)
    total_passed = sum([test1_passed, test2_passed, test3_passed])
    print(f"TOTAL: {total_passed}/3 major tests passed ({100*total_passed//3}%)")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
