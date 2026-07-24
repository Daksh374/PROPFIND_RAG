import React, { useState, useEffect } from 'react';
import { SlidersHorizontal, MapPin, Home, Banknote, Train, Users } from 'lucide-react';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const PROPERTY_TYPES = ['APARTMENT', 'BUILDER_FLOOR', 'INDEPENDENT_HOUSE', 'PG'];
const LISTING_TYPES = ['RENT', 'SALE', 'PG'];
const BHK_OPTIONS = [1, 2, 3, 4, 5];

export default function FilterSidebar({ onFilterChange, initialFilters = {} }) {
  const [localities, setLocalities] = useState([]);
  const [filters, setFilters] = useState(initialFilters);

  useEffect(() => {
    fetch(`${API}/properties/localities`)
      .then(r => r.json())
      .then(setLocalities)
      .catch(() => {});
  }, []);

  const update = (key, value) => {
    const newFilters = { ...filters, [key]: value };
    if (!value && value !== 0) delete newFilters[key];
    setFilters(newFilters);
    onFilterChange(newFilters);
  };

  const reset = () => {
    setFilters({});
    onFilterChange({});
  };

  const hasFilters = Object.keys(filters).length > 0;

  return (
    <div className="space-y-5 bg-white p-4 font-sans text-slate-800 sm:p-5">
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <div className="flex items-center gap-2">
          <SlidersHorizontal size={16} className="text-slate-500" />
          <span className="text-sm font-semibold tracking-normal text-slate-950">Filters</span>
        </div>
        {hasFilters && (
          <button
            onClick={reset}
            className="focus-ring rounded-md px-2 py-1 text-xs font-semibold text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-950"
          >
            Clear all
          </button>
        )}
      </div>

      {/* Listing Type */}
      <div>
        <label className="mb-2.5 flex items-center gap-1.5 text-xs font-semibold text-slate-500">
          <Banknote size={13} className="text-slate-400" /> Listing type
        </label>
        <div className="flex flex-wrap gap-2">
          {LISTING_TYPES.map(lt => (
            <button
              key={lt}
              onClick={() => update('listing_type', filters.listing_type === lt ? '' : lt)}
              className={`focus-ring rounded-md border px-3 py-1.5 text-xs font-semibold transition-colors ${
                filters.listing_type === lt
                  ? 'border-slate-900 bg-slate-950 text-white shadow-sm'
                  : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-white hover:text-slate-950'
              }`}
            >
              {lt}
            </button>
          ))}
        </div>
      </div>

      {/* Property Type */}
      <div>
        <label className="mb-2.5 flex items-center gap-1.5 text-xs font-semibold text-slate-500">
          <Home size={13} className="text-slate-400" /> Property type
        </label>
        <div className="flex flex-wrap gap-2">
          {PROPERTY_TYPES.map(pt => (
            <button
              key={pt}
              onClick={() => update('property_type', filters.property_type === pt ? '' : pt)}
              className={`focus-ring rounded-md border px-2.5 py-1.5 text-xs font-semibold transition-colors ${
                filters.property_type === pt
                  ? 'border-slate-900 bg-slate-950 text-white shadow-sm'
                  : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-white hover:text-slate-950'
              }`}
            >
              {pt.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* BHK */}
      <div>
        <label className="mb-2.5 flex items-center gap-1.5 text-xs font-semibold text-slate-500">
          <Users size={13} className="text-slate-400" /> BHK
        </label>
        <div className="flex gap-2">
          {BHK_OPTIONS.map(b => (
            <button
              key={b}
              onClick={() => update('bhk', filters.bhk === b ? null : b)}
              className={`focus-ring h-9 w-9 rounded-md border text-xs font-semibold transition-colors ${
                filters.bhk === b
                  ? 'border-slate-900 bg-slate-950 text-white shadow-sm'
                  : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-white hover:text-slate-950'
              }`}
            >
              {b}
            </button>
          ))}
        </div>
      </div>

      {/* Price Range */}
      <div>
        <label className="mb-2.5 flex items-center gap-1.5 text-xs font-semibold text-slate-500">
          <Banknote size={13} className="text-slate-400" /> Max price
        </label>
        <input
          type="range"
          min="0"
          max="20000000"
          step="50000"
          value={filters.max_price || 20000000}
          onChange={e => update('max_price', Number(e.target.value))}
          className="w-full cursor-pointer accent-slate-950"
        />
        <div className="mt-1.5 flex justify-between text-xs font-medium text-slate-500">
          <span>₹0</span>
          <span className="font-semibold text-slate-950">
            {filters.max_price ? `₹${(filters.max_price / 100000).toFixed(1)} Lakhs` : 'Any Price'}
          </span>
          <span>₹2Cr+</span>
        </div>
      </div>

      {/* Near Metro */}
      <div>
        <label className="mb-2.5 flex items-center gap-1.5 text-xs font-semibold text-slate-500">
          <Train size={13} className="text-slate-400" /> Metro connectivity
        </label>
        <button
          onClick={() => update('near_metro', filters.near_metro ? null : true)}
          className={`focus-ring w-full rounded-md border py-2.5 text-xs font-semibold transition-colors ${
            filters.near_metro
              ? 'border-emerald-200 bg-emerald-50 text-emerald-700 shadow-sm'
              : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-white hover:text-slate-950'
          }`}
        >
          {filters.near_metro ? 'Near metro only' : 'Near metro station'}
        </button>
      </div>

      {/* Locality */}
      <div>
        <label className="mb-2.5 flex items-center gap-1.5 text-xs font-semibold text-slate-500">
          <MapPin size={13} className="text-slate-400" /> Locality
        </label>
        <select
          value={filters.locality || ''}
          onChange={e => update('locality', e.target.value)}
          className="focus-ring w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-800 focus:border-slate-300 focus:bg-white"
        >
          <option value="">All Delhi NCR Localities</option>
          {localities.slice(0, 50).map(l => (
            <option key={l} value={l}>{l}</option>
          ))}
        </select>
      </div>
    </div>
  );
}
