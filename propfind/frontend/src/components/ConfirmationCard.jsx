import React, { useState, useEffect } from 'react';
import { CheckCircle, XCircle, Calendar, MessageSquare, AlertTriangle, User, Mail, Clock, Edit3 } from 'lucide-react';

export default function ConfirmationCard({ pending, onConfirm, onCancel }) {
  if (!pending) return null;

  const isVisit = pending.tool_name === 'schedule_visit';
  const isInquiry = pending.tool_name === 'send_owner_inquiry';
  const args = pending.args || {};

  const isGenericUser = name => !name || name.toLowerCase() === 'user' || name.toLowerCase() === 'visitor';
  const isGenericEmail = email => !email || email.includes('example.com');

  const [userName, setUserName] = useState(isGenericUser(args.user_name) ? '' : args.user_name);
  const [userEmail, setUserEmail] = useState(isGenericEmail(args.user_email) ? '' : args.user_email);
  const [scheduledDatetime, setScheduledDatetime] = useState(args.scheduled_datetime || '');
  const [notes, setNotes] = useState(args.notes || '');
  const [message, setMessage] = useState(args.message || '');

  useEffect(() => {
    setUserName(isGenericUser(args.user_name) ? '' : args.user_name);
    setUserEmail(isGenericEmail(args.user_email) ? '' : args.user_email);
    setScheduledDatetime(args.scheduled_datetime || '');
    setNotes(args.notes || '');
    setMessage(args.message || '');
  }, [pending]);

  const handleExecute = () => {
    const updatedPending = {
      ...pending,
      args: {
        ...args,
        user_name: userName.trim() || 'Visitor',
        user_email: userEmail.trim() || 'visitor@example.com',
        scheduled_datetime: scheduledDatetime.trim() || 'As requested',
        notes: notes.trim(),
        message: message.trim() || args.message || '',
      },
    };
    onConfirm('confirmed', updatedPending);
  };

  const confirmLabel = isVisit ? 'Confirm visit' : 'Send inquiry';

  return (
    <div className="ml-11 animate-slide-up">
      <div className="max-w-lg rounded-lg border border-amber-200 bg-amber-50 p-4 font-sans shadow-sm">
        <div className="mb-3 flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-md border border-amber-200 bg-white">
            <AlertTriangle size={18} className="text-amber-700" />
          </div>
          <div>
            <p className="text-sm font-semibold text-amber-950">Confirmation required</p>
            <p className="text-xs font-medium text-amber-700">
              {isVisit ? 'Fill in your visit details before scheduling.' : 'Review your message before sending.'}
            </p>
          </div>
        </div>

        <div className="mb-4 space-y-3 rounded-md border border-amber-100 bg-white p-3.5 text-xs text-slate-700">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2">
            <span className="font-semibold text-slate-500">Property ID</span>
            <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 font-semibold text-slate-950">{args.property_id}</span>
          </div>

          {isVisit && (
            <>
              <div>
                <label className="mb-1 flex items-center gap-1 text-[11px] font-semibold text-slate-500">
                  <User size={12} className="text-slate-400" /> Full name
                </label>
                <input
                  type="text"
                  value={userName}
                  onChange={e => setUserName(e.target.value)}
                  placeholder="Enter your full name"
                  className="focus-ring w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-800 transition-colors focus:border-slate-300 focus:bg-white"
                />
              </div>

              <div>
                <label className="mb-1 flex items-center gap-1 text-[11px] font-semibold text-slate-500">
                  <Mail size={12} className="text-slate-400" /> Email address
                </label>
                <input
                  type="email"
                  value={userEmail}
                  onChange={e => setUserEmail(e.target.value)}
                  placeholder="Enter your email address"
                  className="focus-ring w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-800 transition-colors focus:border-slate-300 focus:bg-white"
                />
              </div>

              <div>
                <label className="mb-1 flex items-center gap-1 text-[11px] font-semibold text-slate-500">
                  <Clock size={12} className="text-slate-400" /> Preferred date and time
                </label>
                <input
                  type="text"
                  value={scheduledDatetime}
                  onChange={e => setScheduledDatetime(e.target.value)}
                  placeholder="e.g. Tomorrow 11:00 AM, 2026-07-25 10:00 AM"
                  className="focus-ring w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-900 transition-colors focus:border-slate-300 focus:bg-white"
                />
              </div>

              <div>
                <label className="mb-1 flex items-center gap-1 text-[11px] font-semibold text-slate-500">
                  <Edit3 size={12} className="text-slate-400" /> Notes
                </label>
                <input
                  type="text"
                  value={notes}
                  onChange={e => setNotes(e.target.value)}
                  placeholder="e.g. Prefer morning slot, interested in parking space"
                  className="focus-ring w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-800 transition-colors focus:border-slate-300 focus:bg-white"
                />
              </div>
            </>
          )}

          {isInquiry && (
            <>
              <div>
                <label className="mb-1 flex items-center gap-1 text-[11px] font-semibold text-slate-500">
                  <User size={12} className="text-slate-400" /> Full name
                </label>
                <input
                  type="text"
                  value={userName}
                  onChange={e => setUserName(e.target.value)}
                  placeholder="Enter your full name (e.g. John Doe)"
                  className="focus-ring w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-800 transition-colors focus:border-slate-300 focus:bg-white"
                />
              </div>

              <div>
                <label className="mb-1 flex items-center gap-1 text-[11px] font-semibold text-slate-500">
                  <MessageSquare size={12} className="text-slate-400" /> Message to owner
                </label>
                <textarea
                  value={message}
                  onChange={e => setMessage(e.target.value)}
                  rows={2}
                  placeholder="Write your inquiry message..."
                  className="focus-ring w-full resize-none rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-800 transition-colors focus:border-slate-300 focus:bg-white"
                />
              </div>
            </>
          )}
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleExecute}
            className="focus-ring flex flex-1 items-center justify-center gap-2 rounded-md bg-slate-950 py-2.5 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-slate-800"
          >
            <CheckCircle size={16} />
            {confirmLabel}
          </button>
          <button
            onClick={onCancel}
            className="focus-ring flex flex-1 items-center justify-center gap-2 rounded-md border border-slate-200 bg-white py-2.5 text-xs font-semibold text-slate-600 shadow-sm transition-colors hover:bg-slate-50 hover:text-slate-950"
          >
            <XCircle size={16} />
            Cancel Action
          </button>
        </div>
      </div>
    </div>
  );
}
