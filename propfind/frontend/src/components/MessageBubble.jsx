import React from 'react';
import { Bot, User, Database, Zap, AlertCircle, CheckCircle, XCircle } from 'lucide-react';

function formatMarkdown(text) {
  if (!text) return '';
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
  return escaped
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code class="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 font-mono text-xs text-slate-800">$1</code>')
    .replace(/\n/g, '<br/>');
}

export default function MessageBubble({ message }) {
  const isUser = message.role === 'user';

  // Badge configurations based on engine/type
  const typeConfig = {
    rag: { label: 'RAG Search', color: 'badge-blue', icon: <Database size={12} /> },
    agent: { label: 'Agent Executed', color: 'badge-indigo', icon: <Zap size={12} /> },
    confirmation: { label: 'Action Required', color: 'badge-yellow', icon: <AlertCircle size={12} /> },
    error: { label: 'Error', color: 'badge-red', icon: <AlertCircle size={12} /> },
    success: { label: 'Completed', color: 'badge-green', icon: <CheckCircle size={12} /> },
    cancelled: { label: 'Cancelled', color: 'badge-red', icon: <XCircle size={12} /> },
  };

  const key = message.engine === 'agent' || message.type === 'agent'
    ? 'agent'
    : (message.type && typeConfig[message.type])
      ? message.type
      : 'rag';

  const config = typeConfig[key] || typeConfig.rag;

  if (isUser) {
    return (
      <div className="flex animate-slide-up justify-end gap-3">
        <div className="max-w-[82%] sm:max-w-[70%]">
          <div className="rounded-lg bg-slate-950 px-4 py-3 text-sm font-medium leading-relaxed text-white shadow-sm">
            {message.content}
          </div>
        </div>
        <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white shadow-sm">
          <User size={15} className="text-slate-500" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex animate-slide-up gap-3">
      <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white shadow-sm">
        <Bot size={16} className="text-slate-700" />
      </div>
      <div className="flex max-w-[88%] flex-col gap-1.5 sm:max-w-[74%]">
        <div className="flex items-center gap-2">
          <span className={`${config.color} flex items-center gap-1 shadow-2xs`}>
            {config.icon}
            {config.label}
          </span>
          {message.sourceCount > 0 && (
            <span className="text-xs font-medium text-slate-500">
              Based on {message.sourceCount} property listing{message.sourceCount !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm leading-relaxed text-slate-800 shadow-sm">
          {message.content ? (
            <span
              dangerouslySetInnerHTML={{ __html: formatMarkdown(message.content) }}
            />
          ) : null}
          {message.isStreaming && (
            <span className="ml-1 inline-block h-4 w-1 rounded-full bg-slate-900 animate-pulse" />
          )}
        </div>
      </div>
    </div>
  );
}
