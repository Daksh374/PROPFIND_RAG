import React from 'react';
import { Bot, User, Database, Zap, AlertCircle, CheckCircle, XCircle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';

const markdownComponents = {
  p: ({ node, ...props }) => <p className="mb-2 last:mb-0" {...props} />,
  strong: ({ node, ...props }) => <strong className="font-semibold text-slate-950" {...props} />,
  em: ({ node, ...props }) => <em {...props} />,
  a: ({ node, ...props }) => (
    <a className="text-navy-600 underline hover:text-navy-800" target="_blank" rel="noreferrer" {...props} />
  ),
  code: ({ node, ...props }) => (
    <code className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 font-mono text-xs text-slate-800" {...props} />
  ),
  pre: ({ node, ...props }) => (
    <pre className="mb-2 overflow-x-auto rounded border border-slate-200 bg-slate-50 p-2 font-mono text-xs text-slate-800 last:mb-0 [&>code]:border-0 [&>code]:bg-transparent [&>code]:p-0" {...props} />
  ),
  ul: ({ node, ...props }) => <ul className="mb-2 list-disc space-y-1 pl-5 last:mb-0" {...props} />,
  ol: ({ node, ...props }) => <ol className="mb-2 list-decimal space-y-1 pl-5 last:mb-0" {...props} />,
  li: ({ node, ...props }) => <li {...props} />,
  hr: ({ node, ...props }) => <hr className="my-3 border-slate-200" {...props} />,
  table: ({ node, ...props }) => (
    <div className="mb-2 overflow-x-auto rounded border border-slate-200 last:mb-0">
      <table className="w-full border-collapse text-xs" {...props} />
    </div>
  ),
  thead: ({ node, ...props }) => <thead className="bg-slate-50" {...props} />,
  tr: ({ node, ...props }) => <tr className="border-b border-slate-100 last:border-0" {...props} />,
  th: ({ node, ...props }) => (
    <th className="px-3 py-2 text-left font-semibold text-slate-600" {...props} />
  ),
  td: ({ node, ...props }) => <td className="px-3 py-2 align-top text-slate-800" {...props} />,
};

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
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeRaw]}
              components={markdownComponents}
            >
              {message.content}
            </ReactMarkdown>
          ) : null}
          {message.isStreaming && (
            <span className="ml-1 inline-block h-4 w-1 rounded-full bg-slate-900 animate-pulse" />
          )}
        </div>
      </div>
    </div>
  );
}
