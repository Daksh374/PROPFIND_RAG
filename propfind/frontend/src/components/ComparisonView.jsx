import React, { useState } from 'react';
import { X, Download, FileText } from 'lucide-react';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function formatPrice(price, listingType) {
  if (listingType === 'SALE') {
    if (price >= 10_000_000) return `₹${(price / 10_000_000).toFixed(2)} Cr`;
    if (price >= 100_000) return `₹${(price / 100_000).toFixed(1)} Lakhs`;
    return `₹${price?.toLocaleString('en-IN')}`;
  }
  return `₹${price?.toLocaleString('en-IN')}/mo`;
}

export default function ComparisonView({ properties, userIdentifier, onClose, onRemove }) {
  const [downloading, setDownloading] = useState(false);
  const [reportUrl, setReportUrl] = useState(null);

  const downloadPDF = async () => {
    setDownloading(true);
    try {
      await fetch(`${API}/agent/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          property_ids: properties.map(p => p.property_id),
          user_identifier: userIdentifier,
        }),
      });

      const pdfRes = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: `generate_comparison_report for ${properties.map(p => p.property_id).join(', ')}`,
          user_identifier: userIdentifier,
        }),
      });

      const reader = pdfRes.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        if (buffer.includes('download_url') || buffer.includes('report_id')) break;
      }

      const match = buffer.match(/"download_url"\s*:\s*"([^"]+)"/);
      if (match) {
        const url = `${API}${match[1]}`;
        setReportUrl(url);
        window.open(url, '_blank');
      }
    } catch (e) {
      console.error('PDF generation error', e);
    } finally {
      setDownloading(false);
    }
  };

  const rows = [
    { label: 'Locality', key: p => p.locality },
    { label: 'Type', key: p => p.property_type?.replace('_', ' ') },
    { label: 'Listing', key: p => p.listing_type },
    { label: 'BHK', key: p => `${p.bhk} BHK` },
    { label: 'Area', key: p => `${p.area_sqft?.toFixed(0)} sq.ft` },
    { label: 'Price', key: p => formatPrice(p.price, p.listing_type) },
    { label: 'Price/sqft', key: p => `₹${p.area_sqft ? ((p.price / p.area_sqft) | 0).toLocaleString() : '—'}` },
    { label: 'Near Metro', key: p => p.near_metro ? 'Yes' : 'No' },
    { label: 'Metro Dist', key: p => p.metro_distance_km ? `${p.metro_distance_km?.toFixed(1)} km` : '—' },
    { label: 'Amenities', key: p => (p.amenities || []).slice(0, 5).join(', ') || 'None' },
  ];

  return (
    <div className="fixed inset-0 z-50 flex animate-fade-in items-center justify-center bg-slate-950/40 p-4 backdrop-blur-sm">
      <div className="flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-xl">
        <div className="flex items-center justify-between gap-4 border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
          <div className="flex items-center gap-2.5">
            <FileText size={19} className="text-slate-500" />
            <h2 className="text-base font-semibold text-slate-950">Property Comparison</h2>
            <span className="badge-indigo">{properties.length} properties</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={downloadPDF}
              disabled={downloading}
              className="focus-ring flex items-center gap-2 rounded-md bg-slate-950 px-3 py-2 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-slate-800 disabled:opacity-50 sm:px-4"
            >
              <Download size={14} />
              <span className="hidden sm:inline">{downloading ? 'Generating PDF...' : 'Download PDF'}</span>
            </button>
            <button
              onClick={onClose}
              className="focus-ring rounded-md p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-2">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="w-36 bg-slate-50 px-4 py-3 text-left text-xs font-semibold text-slate-500">
                  Specification
                </th>
                {properties.map(p => (
                  <th key={p.property_id} className="min-w-[220px] px-4 py-3 text-left">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-xs font-semibold leading-snug text-slate-950">{p.title}</p>
                        <p className="text-xs font-medium text-slate-500">{p.property_id}</p>
                      </div>
                      <button
                        onClick={() => onRemove(p.property_id)}
                        className="focus-ring flex-shrink-0 rounded-md p-1 text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600"
                        title="Remove from comparison"
                      >
                        <X size={14} />
                      </button>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={row.label} className={`border-b border-slate-100 ${i % 2 === 0 ? 'bg-slate-50/50' : 'bg-white'}`}>
                  <td className="bg-slate-50 px-4 py-3 text-xs font-semibold text-slate-500">{row.label}</td>
                  {properties.map(p => (
                    <td key={p.property_id} className="px-4 py-3 text-xs font-medium text-slate-800">
                      {row.key(p)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {reportUrl && (
          <div className="border-t border-emerald-200 bg-emerald-50 px-6 py-3">
            <p className="text-xs font-semibold text-emerald-800">
              PDF report generated.{' '}
              <a href={reportUrl} target="_blank" rel="noreferrer" className="underline hover:text-emerald-900 ml-1">
                View PDF
              </a>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
