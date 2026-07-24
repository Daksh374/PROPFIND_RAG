import React, { useState } from 'react';
import { MapPin, Maximize2, Train, CheckSquare, Square, MessageSquare, Eye, ChevronDown, ChevronUp } from 'lucide-react';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function formatPrice(price, listingType) {
  if (listingType === 'SALE') {
    if (price >= 10_000_000) return `₹${(price / 10_000_000).toFixed(2)} Cr`;
    if (price >= 100_000) return `₹${(price / 100_000).toFixed(1)} Lakhs`;
    return `₹${price?.toLocaleString('en-IN')}`;
  }
  return `₹${price?.toLocaleString('en-IN')}/mo`;
}

const LISTING_COLORS = {
  RENT: 'badge-blue',
  SALE: 'badge-green',
  PG: 'badge-purple',
};

export default function PropertyCard({ property: prop, isSelected, onCompareToggle, userIdentifier }) {
  const [expanded, setExpanded] = useState(false);
  const [inquiring, setInquiring] = useState(false);
  const [inquiryStatus, setInquiryStatus] = useState('');

  const handleInquire = async () => {
    const message = `Hi, I'm interested in ${prop.title}. Could you please share more details?`;
    setInquiring(true);
    setInquiryStatus('');
    try {
      const res = await fetch(`${API}/chat/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_identifier: userIdentifier,
          decision: 'confirmed',
          pending_confirmation: {
            tool_name: 'send_owner_inquiry',
            tool_call_id: 'direct',
            args: {
              property_id: prop.property_id,
              message,
              user_name: userIdentifier,
            },
          },
        }),
      });
      if (!res.ok) throw new Error('Inquiry failed');
      setInquiryStatus('Inquiry sent');
      window.dispatchEvent(new Event('activity-updated'));
    } catch (e) {
      setInquiryStatus('Use chat to send');
    } finally {
      setInquiring(false);
    }
  };

  return (
    <div className={`prop-card flex flex-col justify-between overflow-hidden rounded-lg border bg-white ${isSelected ? 'border-slate-950 ring-2 ring-slate-200' : 'border-slate-200'}`}>
      <div>
        <div className="p-4">
          <div className="mb-3 flex items-start justify-between gap-2">
            <div className="flex flex-wrap gap-1.5">
              <span className={LISTING_COLORS[prop.listing_type] || 'badge-blue'}>
                {prop.listing_type}
              </span>
              <span className="badge-purple">{prop.bhk} BHK</span>
              {prop.near_metro && (
                <span className="badge-green flex items-center gap-1">
                  <Train size={10} />Metro
                </span>
              )}
            </div>
            <button
              onClick={() => onCompareToggle(prop)}
              className={`focus-ring flex-shrink-0 rounded-md p-1.5 transition-colors ${
                isSelected ? 'bg-slate-950 text-white' : 'text-slate-400 hover:bg-slate-100 hover:text-slate-700'
              }`}
              title={isSelected ? 'Remove from comparison' : 'Add to comparison'}
            >
              {isSelected ? <CheckSquare size={18} /> : <Square size={18} />}
            </button>
          </div>

          <h3 className="mb-1 line-clamp-2 text-sm font-semibold leading-snug text-slate-950">
            {prop.title}
          </h3>

          <div className="mb-3 flex items-center gap-1 text-xs font-medium text-slate-500">
            <MapPin size={12} className="text-slate-400" />
            <span>{prop.locality}</span>
          </div>

          <div className="mb-3 flex items-center gap-4 border-b border-slate-100 pb-3">
            <div className="flex items-center gap-1 text-xs font-medium text-slate-600">
              <Maximize2 size={12} className="text-slate-400" />
              <span>{prop.area_sqft?.toFixed(0)} sq.ft</span>
            </div>
            {prop.metro_distance_km && (
              <div className="flex items-center gap-1 text-xs font-medium text-slate-600">
                <Train size={12} className="text-slate-400" />
                <span>{prop.metro_distance_km?.toFixed(1)} km to metro</span>
              </div>
            )}
          </div>

          <div className="mb-3 text-xl font-semibold text-slate-950">
            {formatPrice(prop.price, prop.listing_type)}
            <span className="ml-1.5 text-xs font-medium text-slate-400">
              (₹{prop.area_sqft ? ((prop.price / prop.area_sqft) | 0).toLocaleString() : '—'}/sqft)
            </span>
          </div>

          {prop.amenities?.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-1.5">
              {prop.amenities.slice(0, 3).map(a => (
                <span key={a} className="rounded-md bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
                  {a}
                </span>
              ))}
              {prop.amenities.length > 3 && (
                <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">
                  +{prop.amenities.length - 3} more
                </span>
              )}
            </div>
          )}

          {expanded && (
            <div className="mb-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">
              <p className="mb-1">{prop.description_text}</p>
              {prop.listing_type === 'PG' && (
                <div className="mt-2 space-y-1 font-medium">
                  {prop.food_included && <p>Food: {prop.food_type}</p>}
                  <p>Preference: {prop.gender_preference}</p>
                  <p>Occupancy: {prop.occupancy_type?.replace('_', ' ')}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 border-t border-slate-100 bg-slate-50 px-3 py-2.5">
        <button
          onClick={() => setExpanded(e => !e)}
          className="focus-ring flex items-center gap-1 rounded-md px-1 py-1 text-xs font-semibold text-slate-500 transition-colors hover:text-slate-800"
        >
          <Eye size={13} />
          {expanded ? 'Less' : 'More Details'}
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>

        {inquiryStatus && (
          <span className="ml-auto text-xs font-semibold text-slate-500">{inquiryStatus}</span>
        )}
        <button
          onClick={handleInquire}
          disabled={inquiring}
          className={`${inquiryStatus ? '' : 'ml-auto'} focus-ring flex items-center gap-1.5 rounded-md bg-slate-950 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-slate-800 disabled:opacity-50`}
        >
          <MessageSquare size={13} />
          {inquiring ? 'Sending...' : 'Inquire'}
        </button>
      </div>
    </div>
  );
}
