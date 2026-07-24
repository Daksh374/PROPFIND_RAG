import React, { useState, useEffect, useCallback } from 'react';
import { MessageSquare, Building2, Calendar, ChevronRight, SlidersHorizontal } from 'lucide-react';
import ChatPanel from './components/ChatPanel';
import FilterSidebar from './components/FilterSidebar';
import PropertyCard from './components/PropertyCard';
import ComparisonView from './components/ComparisonView';
import VisitsTab from './components/VisitsTab';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function App() {
  const [activeTab, setActiveTab] = useState('chat');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [properties, setProperties] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({});
  const [compareList, setCompareList] = useState([]);
  const [showComparison, setShowComparison] = useState(false);
  const [userIdentifier] = useState('user_' + Math.random().toString(36).slice(2, 8));

  const fetchProperties = useCallback(async (newFilters = filters, newPage = page) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.append('page', newPage);
      params.append('page_size', '12');
      Object.entries(newFilters).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') params.append(k, v);
      });
      const res = await fetch(`${API}/properties?${params}`);
      const data = await res.json();
      setProperties(data.results || []);
      setTotal(data.total || 0);
    } catch (e) {
      console.error('Failed to fetch properties', e);
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => {
    if (activeTab === 'browse') {
      fetchProperties(filters, page);
    }
  }, [activeTab, filters, page, fetchProperties]);

  const handleFilterChange = (newFilters) => {
    setFilters(newFilters);
    setPage(1);
    fetchProperties(newFilters, 1);
  };

  const handleCompareToggle = (prop) => {
    setCompareList(prev => {
      const exists = prev.find(p => p.property_id === prop.property_id);
      if (exists) return prev.filter(p => p.property_id !== prop.property_id);
      if (prev.length >= 4) return prev;
      return [...prev, prop];
    });
  };

  const tabs = [
    { id: 'chat', label: 'Assistant', icon: <MessageSquare size={16} /> },
    { id: 'browse', label: 'Properties', icon: <Building2 size={16} /> },
    { id: 'visits', label: 'Activity', icon: <Calendar size={16} /> },
  ];

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-[#f7f8fb] font-sans text-slate-950">
      <header className="z-30 flex flex-shrink-0 items-center gap-3 border-b border-slate-200 bg-white/95 px-4 py-3 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-900 bg-slate-950 text-sm font-bold text-white shadow-sm">
            PF
          </div>
          <div className="min-w-0">
            <div className="text-base font-semibold leading-none tracking-normal text-slate-950">PropFind</div>
            <div className="mt-1 hidden text-xs font-medium text-slate-500 sm:block">Delhi NCR property</div>
          </div>
        </div>

        <nav className="ml-auto flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 p-1">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`focus-ring flex h-8 items-center gap-2 rounded-md px-3 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-white text-slate-950 shadow-sm'
                  : 'text-slate-500 hover:bg-white/70 hover:text-slate-900'
              }`}
            >
              {tab.icon}
              <span className="hidden sm:inline">{tab.label}</span>
            </button>
          ))}
        </nav>

        {activeTab === 'browse' && (
          <button
            onClick={() => setSidebarOpen(open => !open)}
            className="focus-ring hidden h-9 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 lg:flex"
          >
            <SlidersHorizontal size={15} />
            Filters
          </button>
        )}

        {compareList.length > 0 && (
          <button
            onClick={() => setShowComparison(true)}
            className="focus-ring flex h-9 items-center gap-1.5 rounded-md border border-slate-300 bg-slate-950 px-3 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-slate-800"
          >
            <span>Compare ({compareList.length})</span>
            <ChevronRight size={14} />
          </button>
        )}
      </header>

      <div className="flex flex-1 flex-col overflow-hidden lg:flex-row">
        {sidebarOpen && activeTab === 'browse' && (
          <aside className="max-h-72 w-full flex-shrink-0 overflow-y-auto border-b border-slate-200 bg-white lg:max-h-none lg:w-72 lg:border-b-0 lg:border-r">
            <FilterSidebar onFilterChange={handleFilterChange} initialFilters={filters} />
          </aside>
        )}

        <main className="relative flex flex-1 flex-col overflow-hidden bg-[#f7f8fb]">
          <div className={activeTab === 'chat' ? 'flex-1 flex flex-col h-full overflow-hidden' : 'hidden'}>
            <ChatPanel userIdentifier={userIdentifier} />
          </div>

          <div className={activeTab === 'browse' ? 'flex-1 overflow-y-auto p-4 sm:p-6 h-full' : 'hidden'}>
            <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h1 className="text-lg font-semibold text-slate-950">Property Inventory</h1>
                <p className="mt-1 text-sm font-medium text-slate-500">
                  {loading ? 'Searching property database...' : `${total.toLocaleString()} matching listings`}
                </p>
              </div>
              <button
                onClick={() => setSidebarOpen(open => !open)}
                className="focus-ring flex h-9 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 lg:hidden"
              >
                <SlidersHorizontal size={15} />
                Filters
              </button>
              <p className="sr-only">
                {loading ? 'Searching property database...' : `${total.toLocaleString()} listings found`}
              </p>
              {compareList.length > 0 && (
                <span className="badge-gold">
                  {compareList.length}/4 selected for comparison
                </span>
              )}
            </div>

            {/* Property Grid */}
            {loading ? (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="h-64 rounded-lg shimmer border border-slate-200" />
                ))}
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {properties.map(prop => (
                    <PropertyCard
                      key={prop.property_id}
                      property={prop}
                      isSelected={!!compareList.find(p => p.property_id === prop.property_id)}
                      onCompareToggle={handleCompareToggle}
                      userIdentifier={userIdentifier}
                    />
                  ))}
                </div>

                {/* Pagination */}
                {total > 12 && (
                  <div className="mt-8 flex items-center justify-center gap-3 pb-4">
                    <button
                      onClick={() => setPage(p => Math.max(1, p - 1))}
                      disabled={page === 1}
                      className="focus-ring rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      Previous
                    </button>
                    <span className="text-sm font-medium text-slate-500">
                      Page {page} of {Math.ceil(total / 12)}
                    </span>
                    <button
                      onClick={() => setPage(p => p + 1)}
                      disabled={page >= Math.ceil(total / 12)}
                      className="focus-ring rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      Next
                    </button>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Visits & Inquiries Tab Panel */}
          <div className={activeTab === 'visits' ? 'flex-1 overflow-y-auto p-4 sm:p-6 h-full' : 'hidden'}>
            <VisitsTab activeTab={activeTab} userIdentifier={userIdentifier} />
          </div>
        </main>
      </div>

      {/* Comparison Overlay */}
      {showComparison && (
        <ComparisonView
          properties={compareList}
          userIdentifier={userIdentifier}
          onClose={() => setShowComparison(false)}
          onRemove={(pid) => setCompareList(prev => prev.filter(p => p.property_id !== pid))}
        />
      )}
    </div>
  );
}
