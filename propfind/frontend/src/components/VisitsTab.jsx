import React, { useState, useEffect } from 'react';
import { Calendar, MessageSquare, RefreshCw, Clock, CheckCircle, XCircle, AlertCircle, Loader, Trash2 } from 'lucide-react';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const STATUS_CONFIG = {
  pending_confirmation: { label: 'Pending', color: 'badge-yellow', icon: <Clock size={11} /> },
  scheduled: { label: 'Scheduled', color: 'badge-indigo', icon: <CheckCircle size={11} /> },
  confirmed: { label: 'Confirmed', color: 'badge-green', icon: <CheckCircle size={11} /> },
  completed: { label: 'Completed', color: 'badge-green', icon: <CheckCircle size={11} /> },
  cancelled: { label: 'Cancelled', color: 'badge-red', icon: <XCircle size={11} /> },
  sent: { label: 'Sent', color: 'badge-green', icon: <CheckCircle size={11} /> },
};

function StatusBadge({ status }) {
  const config = STATUS_CONFIG[status] || { label: status, color: 'badge-blue', icon: <AlertCircle size={11} /> };
  return (
    <span className={`${config.color} flex items-center gap-1`}>
      {config.icon}
      {config.label}
    </span>
  );
}

export default function VisitsTab({ activeTab }) {
  const [visits, setVisits] = useState([]);
  const [inquiries, setInquiries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState('visits');

  const load = async () => {
    setLoading(true);
    try {
      const [vRes, iRes] = await Promise.all([
        fetch(`${API}/agent/visits`),
        fetch(`${API}/agent/inquiries`),
      ]);
      const vData = await vRes.json();
      const iData = await iRes.json();
      setVisits(Array.isArray(vData) ? vData : []);
      setInquiries(Array.isArray(iData) ? iData : []);
    } catch (e) {
      console.error('Failed to load visits/inquiries', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'visits' || !activeTab) {
      load();
    }
  }, [activeTab]);

  useEffect(() => {
    const handleActivityUpdate = () => {
      load();
    };
    window.addEventListener('activity-updated', handleActivityUpdate);
    return () => window.removeEventListener('activity-updated', handleActivityUpdate);
  }, []);

  const deleteAllInquiries = async () => {
    if (!window.confirm('Are you sure you want to delete all inquiries?')) return;
    try {
      await fetch(`${API}/agent/inquiries`, { method: 'DELETE' });
      setInquiries([]);
    } catch (e) {
      alert('Failed to delete inquiries.');
    }
  };

  const deleteSingleInquiry = async (id) => {
    try {
      await fetch(`${API}/agent/inquiries/${id}`, { method: 'DELETE' });
      setInquiries(prev => prev.filter(i => i.id !== id));
    } catch (e) {
      alert('Failed to delete inquiry.');
    }
  };

  const deleteAllVisits = async () => {
    if (!window.confirm('Are you sure you want to delete all scheduled visits?')) return;
    try {
      await fetch(`${API}/agent/visits`, { method: 'DELETE' });
      setVisits([]);
    } catch (e) {
      alert('Failed to delete visits.');
    }
  };

  const deleteSingleVisit = async (id) => {
    try {
      await fetch(`${API}/agent/visits/${id}`, { method: 'DELETE' });
      setVisits(prev => prev.filter(v => v.id !== id));
    } catch (e) {
      alert('Failed to delete visit.');
    }
  };

  return (
    <div className="flex-1 overflow-y-auto bg-[#f7f8fb] font-sans">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-950">Activity</h1>
          <p className="mt-1 text-sm font-medium text-slate-500">Track scheduled visits and owner inquiries.</p>
        </div>

        <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 p-1">
          <button
            onClick={() => setActiveSection('visits')}
            className={`focus-ring flex h-8 items-center gap-2 rounded-md px-3 text-xs font-semibold transition-colors ${
              activeSection === 'visits'
                ? 'bg-white text-slate-950 shadow-sm'
                : 'text-slate-500 hover:bg-white/70 hover:text-slate-900'
            }`}
          >
            <Calendar size={15} />
            Visits ({visits.length})
          </button>
          <button
            onClick={() => setActiveSection('inquiries')}
            className={`focus-ring flex h-8 items-center gap-2 rounded-md px-3 text-xs font-semibold transition-colors ${
              activeSection === 'inquiries'
                ? 'bg-white text-slate-950 shadow-sm'
                : 'text-slate-500 hover:bg-white/70 hover:text-slate-900'
            }`}
          >
            <MessageSquare size={15} />
            Inquiries ({inquiries.length})
          </button>
        </div>

        <div className="flex items-center gap-2">
          {activeSection === 'inquiries' && inquiries.length > 0 && (
            <button
              onClick={deleteAllInquiries}
              className="focus-ring flex items-center gap-1.5 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700 shadow-sm transition-colors hover:bg-rose-100"
              title="Delete all owner inquiries"
            >
              <Trash2 size={14} />
              Delete inquiries
            </button>
          )}

          {activeSection === 'visits' && visits.length > 0 && (
            <button
              onClick={deleteAllVisits}
              className="focus-ring flex items-center gap-1.5 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700 shadow-sm transition-colors hover:bg-rose-100"
              title="Delete all visits"
            >
              <Trash2 size={14} />
              Delete visits
            </button>
          )}

          <button
            onClick={load}
            className="focus-ring rounded-md border border-slate-200 bg-white p-2 text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-950"
            title="Refresh Data"
          >
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48">
          <Loader className="animate-spin text-slate-700" size={28} />
        </div>
      ) : activeSection === 'visits' ? (
        visits.length === 0 ? (
          <EmptyState icon={<Calendar size={36} />} title="No visits scheduled" desc="You can schedule property visits directly via the AI chat panel." />
        ) : (
          <div className="max-w-4xl space-y-3">
            {visits.map(v => (
              <div key={v.id} className="group relative rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-sm font-semibold text-slate-950">{v.property_id}</span>
                      <StatusBadge status={v.status} />
                    </div>
                    <div className="space-y-1.5 text-xs font-medium text-slate-600">
                      <div className="flex items-center gap-1.5 font-semibold text-slate-900">
                        <Calendar size={13} />
                        <span>{v.scheduled_datetime}</span>
                      </div>
                      <div>Visitor: <span className="font-semibold text-slate-800">{v.user_name}</span> ({v.user_email})</div>
                      {v.notes && <div className="rounded-md border border-slate-100 bg-slate-50 p-2 text-slate-700">{v.notes}</div>}
                    </div>
                  </div>

                  <button
                    onClick={() => deleteSingleVisit(v.id)}
                    className="focus-ring rounded-md p-2 text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600"
                    title="Delete visit"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )
      ) : (
        inquiries.length === 0 ? (
          <EmptyState icon={<MessageSquare size={36} />} title="No owner inquiries sent" desc="Send inquiry messages via property cards or the AI chat panel." />
        ) : (
          <div className="max-w-4xl space-y-3">
            {inquiries.map(inq => (
              <div key={inq.id} className="group relative rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-sm font-semibold text-slate-950">Property: {inq.property_id}</span>
                      <StatusBadge status={inq.status} />
                    </div>
                    <div className="space-y-1.5 text-xs font-medium text-slate-600">
                      <div>From: <span className="font-semibold text-slate-800">{inq.user_name}</span></div>
                      {inq.owner_id && <div>Owner: <span className="font-semibold text-slate-800">{inq.owner_id}</span></div>}
                      <div className="rounded-md border border-slate-100 bg-slate-50 p-3 leading-relaxed text-slate-800">
                        {inq.message?.slice(0, 200)}{inq.message?.length > 200 ? '...' : ''}
                      </div>
                      <div className="text-slate-400 font-normal">{new Date(inq.created_at).toLocaleString()}</div>
                    </div>
                  </div>

                  <button
                    onClick={() => deleteSingleInquiry(inq.id)}
                    className="focus-ring rounded-md p-2 text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600"
                    title="Delete inquiry"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  );
}

function EmptyState({ icon, title, desc }) {
  return (
    <div className="flex h-64 flex-col items-center justify-center gap-3 rounded-lg border border-slate-200 bg-white p-8 text-center shadow-sm">
      <div className="rounded-lg bg-slate-100 p-4 text-slate-500">{icon}</div>
      <p className="text-base font-semibold text-slate-950">{title}</p>
      <p className="text-xs text-slate-500 max-w-xs leading-relaxed">{desc}</p>
    </div>
  );
}
