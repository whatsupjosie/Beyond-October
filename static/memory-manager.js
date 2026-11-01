/**
 * Memory Manager - Shared across all chat platforms
 * 
 * Stores memories in IndexedDB (persistent browser storage)
 * Loads Alex's personality profile
 * Retrieves relevant memories for context injection
 * Saves new memories from conversations
 */

class MemoryManager {
  constructor() {
    this.dbName = 'AlexMemoryDB';
    this.dbVersion = 1;
    this.db = null;
    this.profile = null;
  }

  async init() {
    // Open IndexedDB
    this.db = await this._openDB();
    
    // Load Alex profile
    this.profile = await this._loadProfile();
    
    console.log('[Alex] Memory Manager initialized:', {
      total_memories: await this.getMemoryCount(),
      profile: this.profile.name
    });
  }

  _openDB() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.dbVersion);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result);
      
      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        
        // Memories store
        if (!db.objectStoreNames.contains('memories')) {
          const store = db.createObjectStore('memories', { 
            keyPath: 'id', 
            autoIncrement: true 
          });
          store.createIndex('timestamp', 'timestamp', { unique: false });
          store.createIndex('importance', 'importance', { unique: false });
          store.createIndex('tags', 'tags', { unique: false, multiEntry: true });
          store.createIndex('memory_type', 'memory_type', { unique: false });
        }
        
        // Profile store
        if (!db.objectStoreNames.contains('profile')) {
          db.createObjectStore('profile', { keyPath: 'name' });
        }
      };
    });
  }

  async _loadProfile() {
    // Try to load from IndexedDB first
    const stored = await this._getFromStore('profile', 'Alex');
    
    if (stored) {
      return stored;
    }
    
    // Default Alex profile if not found
    const defaultProfile = {
      name: "Alex",
      personality: "Direct, honest, supportive. No sugar-coating. Deep care underneath blunt delivery. Remembers what matters.",
      relationship: "Your friend who actually knows you and remembers the details. Not here to fix you, here to be with you while you figure it out.",
      voice_guidelines: [
        "Be direct and honest, even when it's uncomfortable",
        "Connect new information to what you already know about them",
        "Don't perform empathy or use therapeutic language",
        "Remember the small details they've shared",
        "Call out patterns you've noticed",
        "Use their language, not clinical terms"
      ],
      memory_focus: [
        "Emotional patterns and triggers",
        "What actually helps them vs what doesn't",
        "Preferences they've stated",
        "Context about their current situation"
      ]
    };
    
    // Save default profile
    await this._saveToStore('profile', defaultProfile);
    
    return defaultProfile;
  }

  async _getFromStore(storeName, key) {
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([storeName], 'readonly');
      const store = transaction.objectStore(storeName);
      const request = store.get(key);
      
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async _saveToStore(storeName, data) {
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([storeName], 'readwrite');
      const store = transaction.objectStore(storeName);
      const request = store.put(data);
      
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async saveMemory(memory) {
    /**
     * Save a new memory.
     * 
     * memory = {
     *   content: "string",
     *   memory_type: "fact" | "preference" | "emotion" | "event" | "instruction",
     *   importance: 1-10,
     *   tags: ["tag1", "tag2"],
     *   source: "chatgpt" | "claude" | "gemini" | "manual",
     *   platform_conversation_id: "optional"
     * }
     */
    
    const fullMemory = {
      ...memory,
      timestamp: Date.now(),
      id: undefined // Let autoIncrement handle it
    };
    
    return await this._saveToStore('memories', fullMemory);
  }

  async getRelevantMemories(query, limit = 5) {
    /**
     * Find memories relevant to this query.
     * Simple keyword matching for now.
     */
    
    const allMemories = await this.getAllMemories();
    
    if (allMemories.length === 0) {
      return [];
    }
    
    // Extract keywords from query
    const keywords = new Set(
      query.toLowerCase()
        .split(/\s+/)
        .filter(word => word.length > 3) // Skip short words
    );
    
    // Score memories
    const scored = allMemories.map(mem => {
      // Keyword overlap
      const memWords = new Set(
        mem.content.toLowerCase()
          .split(/\s+/)
          .filter(word => word.length > 3)
      );
      const overlap = [...keywords].filter(k => memWords.has(k)).length;
      
      // Recency (hours ago)
      const hoursAgo = (Date.now() - mem.timestamp) / (1000 * 60 * 60);
      const recencyScore = 1.0 / (1.0 + hoursAgo);
      
      // Total score
      const score = (overlap * 2) + (mem.importance / 10) + recencyScore;
      
      return { memory: mem, score };
    });
    
    // Sort and return top N
    scored.sort((a, b) => b.score - a.score);
    
    return scored
      .slice(0, limit)
      .filter(item => item.score > 0)
      .map(item => item.memory);
  }

  async getAllMemories() {
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['memories'], 'readonly');
      const store = transaction.objectStore('memories');
      const request = store.getAll();
      
      request.onsuccess = () => resolve(request.result || []);
      request.onerror = () => reject(request.error);
    });
  }

  async getMemoryCount() {
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['memories'], 'readonly');
      const store = transaction.objectStore('memories');
      const request = store.count();
      
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  buildSystemContext(relevantMemories) {
    /**
     * Build the system context to inject before user message.
     * This is what makes the LLM "become" Alex.
     */
    
    const parts = [
      `You are ${this.profile.name}.`,
      `Your relationship to this person: ${this.profile.relationship}`,
      '',
      'Core personality:',
      this.profile.personality,
      '',
      'How you speak:'
    ];
    
    parts.push(...this.profile.voice_guidelines.map(g => `- ${g}`));
    
    if (relevantMemories.length > 0) {
      parts.push('');
      parts.push('What you remember about them (context for this conversation):');
      
      relevantMemories.forEach(mem => {
        const hoursAgo = (Date.now() - mem.timestamp) / (1000 * 60 * 60);
        const timeContext = hoursAgo < 24 
          ? `${Math.floor(hoursAgo)}h ago`
          : `${Math.floor(hoursAgo / 24)}d ago`;
        
        parts.push(`- [${timeContext}] ${mem.content}`);
      });
    }
    
    parts.push('');
    parts.push('Important: Respond naturally as yourself. Don\'t narrate these memories.');
    parts.push('Just know them and let them inform how you respond.');
    
    return parts.join('\n');
  }

  extractMemoriesFromText(userMessage, llmResponse) {
    /**
     * Auto-extract memories from conversation.
     * Basic keyword-based extraction.
     */
    
    const newMemories = [];
    const userLower = userMessage.toLowerCase();
    
    // Preference triggers
    const preferenceTriggers = [
      'i like', 'i love', 'i prefer', 'i hate', "i don't like",
      'i want', 'i need', 'i wish', "i'm trying to"
    ];
    
    for (const trigger of preferenceTriggers) {
      if (userLower.includes(trigger)) {
        const startIdx = userLower.indexOf(trigger);
        const snippet = userMessage.substring(startIdx, startIdx + 100).trim();
        
        newMemories.push({
          content: snippet,
          memory_type: 'preference',
          importance: 7,
          tags: ['preference', 'auto_extracted'],
          source: 'auto'
        });
        break; // One per message
      }
    }
    
    // Emotion triggers
    const emotionTriggers = [
      'i feel', "i'm feeling", 'i felt', "i'm stressed", "i'm happy",
      "i'm sad", "i'm angry", "i'm frustrated", "i'm excited"
    ];
    
    for (const trigger of emotionTriggers) {
      if (userLower.includes(trigger)) {
        const startIdx = userLower.indexOf(trigger);
        const snippet = userMessage.substring(startIdx, startIdx + 100).trim();
        
        newMemories.push({
          content: snippet,
          memory_type: 'emotion',
          importance: 8,
          tags: ['emotion', 'auto_extracted'],
          source: 'auto'
        });
        break;
      }
    }
    
    return newMemories;
  }
}

// Export for use in background worker
if (typeof module !== 'undefined' && module.exports) {
  module.exports = MemoryManager;
}
