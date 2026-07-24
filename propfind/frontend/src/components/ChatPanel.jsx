import React, { useState, useEffect, useRef } from 'react';
import { Send } from 'lucide-react';
import MessageBubble from './MessageBubble';
import ConfirmationCard from './ConfirmationCard';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function ChatPanel({ userIdentifier }) {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content: "Welcome to **PropFind AI**. Search Delhi NCR listings, compare homes, estimate fair value, schedule visits, or send owner inquiries from one workspace.\n\nWhat kind of property are you looking for?",
      engine: 'rag',
      type: 'rag',
      sourceCount: 0,
    }
  ]);
  const [input, setInput] = useState('');
  const [mode, setMode] = useState('auto');
  const [isStreaming, setIsStreaming] = useState(false);
  const [pendingConfirmation, setPendingConfirmation] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async (text = input) => {
    if (!text.trim() || isStreaming) return;
    setInput('');
    setIsStreaming(true);

    const userMsg = { id: Date.now(), role: 'user', content: text };
    const assistantMsgId = Date.now() + 1;
    const assistantMsg = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      engine: 'rag', // default until SSE stream specifies engine
      type: 'rag',
      sourceCount: 0,
      isStreaming: true,
    };

    setMessages(prev => [...prev, userMsg, assistantMsg]);

    const chatHistory = messages
      .filter(m => m.role !== 'system' && m.id !== 'welcome')
      .slice(-6)
      .map(m => ({ role: m.role === 'assistant' ? 'assistant' : 'user', content: m.content }));

    try {
      const response = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          user_identifier: userIdentifier,
          mode,
          chat_history: chatHistory,
        }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`Chat request failed with status ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let fullText = '';
      let currentEvent = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.trim()) continue;
          if (line.startsWith('event:')) {
            currentEvent = line.slice(6).trim();
            continue;
          }
          if (line.startsWith('data:')) {
            try {
              const data = JSON.parse(line.slice(5).trim());

              if (data.engine) {
                setMessages(prev => prev.map(m =>
                  m.id === assistantMsgId ? { ...m, engine: data.engine, type: data.engine } : m
                ));
              }

              if (currentEvent === 'sources' && Array.isArray(data)) {
                setMessages(prev => prev.map(m =>
                  m.id === assistantMsgId ? { ...m, sourceCount: data.length } : m
                ));
              } else if (data.text) {
                fullText += data.text;
                setMessages(prev => prev.map(m =>
                  m.id === assistantMsgId ? { ...m, content: fullText } : m
                ));
              } else if (data.source_count !== undefined) {
                setMessages(prev => prev.map(m =>
                  m.id === assistantMsgId ? { ...m, sourceCount: data.source_count, isStreaming: false } : m
                ));
              } else if (data.type === 'confirmation_required') {
                setPendingConfirmation(data.pending_confirmation);
                setMessages(prev => prev.map(m =>
                  m.id === assistantMsgId
                    ? { ...m, content: data.response, type: 'confirmation', engine: 'agent', isStreaming: false }
                    : m
                ));
              } else if (data.message) {
                if (data.message !== 'Agent is thinking...' && data.message !== 'Agent is processing...') {
                  fullText += data.message;
                  setMessages(prev => prev.map(m =>
                    m.id === assistantMsgId ? { ...m, content: fullText } : m
                  ));
                }
              }
            } catch (_) {}
          }
        }
      }

      setMessages(prev => prev.map(m =>
        m.id === assistantMsgId ? { ...m, isStreaming: false } : m
      ));
    } catch (e) {
      setMessages(prev => prev.map(m =>
        m.id === assistantMsgId
          ? { ...m, content: 'Connection error. Please ensure the backend server is running.', isStreaming: false, type: 'error' }
          : m
      ));
    } finally {
      setIsStreaming(false);
      window.dispatchEvent(new Event('activity-updated'));
    }
  };

  const handleConfirmation = async (decision, customPending = null) => {
    const payloadPending = customPending || pendingConfirmation;
    if (!payloadPending) return;
    try {
      await fetch(`${API}/chat/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_identifier: userIdentifier,
          decision,
          pending_confirmation: payloadPending,
        }),
      });

      const confirmMsg = {
        id: Date.now(),
        role: 'assistant',
        content: decision === 'confirmed'
          ? '✅ Action confirmed and saved successfully!'
          : '❌ Action cancelled.',
        type: decision === 'confirmed' ? 'success' : 'cancelled',
        engine: 'agent',
      };
      setMessages(prev => [...prev, confirmMsg]);
      setPendingConfirmation(null);
      if (decision === 'confirmed') {
        window.dispatchEvent(new Event('activity-updated'));
      }
    } catch (e) {
      console.error('Confirm failed', e);
    }
  };

  const suggestions = [
    "Find 2BHK apartments in Noida under ₹40,000/month",
    "Compare PROP1001 and PROP1002",
    "What's the fair market price for a 3BHK in Gurgaon?",
    "Show me PGs in Gurgaon with food included",
  ];

  return (
    <div className="flex h-full flex-col bg-[#f7f8fb]">
      <div className="flex-1 space-y-4 overflow-y-auto p-4 sm:p-6">
        {messages.map(msg => (
          <React.Fragment key={msg.id}>
            <MessageBubble message={msg} />
            {msg.type === 'confirmation' && pendingConfirmation && (
              <ConfirmationCard
                pending={pendingConfirmation}
                onConfirm={(decision, customPending) => handleConfirmation(decision || 'confirmed', customPending)}
                onCancel={() => handleConfirmation('cancelled')}
              />
            )}
          </React.Fragment>
        ))}
        <div ref={bottomRef} />
      </div>

      {messages.length <= 2 && (
        <div className="flex flex-wrap gap-2 px-4 pb-3 sm:px-6">
          {suggestions.map((s, i) => (
            <button
              key={i}
              onClick={() => sendMessage(s)}
              className="focus-ring rounded-md border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 shadow-sm transition-colors hover:border-slate-300 hover:text-slate-950"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <div className="border-t border-slate-200 bg-white p-3 shadow-sm sm:p-4">
        <div className="mx-auto flex max-w-5xl flex-col gap-3">
          <div className="flex items-end gap-3">
          <div className="flex-1 relative">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Ask about properties, schedule visits, compare listings..."
              rows={1}
              className="focus-ring w-full resize-none rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 transition-colors placeholder:text-slate-400 focus:border-slate-300 focus:bg-white"
              style={{ minHeight: '46px', maxHeight: '120px' }}
              onInput={e => {
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
              }}
            />
          </div>
          <button
            onClick={() => sendMessage()}
            disabled={!input.trim() || isStreaming}
            className="focus-ring flex h-[46px] w-[46px] flex-shrink-0 items-center justify-center rounded-lg bg-slate-950 text-white shadow-sm transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {isStreaming ? (
              <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <Send size={18} />
            )}
          </button>
        </div>
        </div>
      </div>
    </div>
  );
}
