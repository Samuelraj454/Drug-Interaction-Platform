import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { DRUG_DATASET } from '../data/drugs';
import { Search, FlaskConical, CornerDownLeft } from 'lucide-react';

export default function DrugSearchInput({ value, onChange, placeholder, disabled, icon: Icon }) {
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const containerRef = useRef(null);

  useEffect(() => {
    if (value.trim().length === 0) {
      setSuggestions([]);
      return;
    }

    const searchTerm = value.toLowerCase();
    
    // 1. Prefix matches first
    const prefixMatches = DRUG_DATASET.filter(d => 
      d.name.toLowerCase().startsWith(searchTerm)
    );
    
    // 2. Fuzzy/Contains matches fallback
    const fuzzyMatches = DRUG_DATASET.filter(d => 
      !d.name.toLowerCase().startsWith(searchTerm) && 
      d.name.toLowerCase().includes(searchTerm)
    );

    const combined = [...prefixMatches, ...fuzzyMatches].slice(0, 8);
    setSuggestions(combined);
    setSelectedIndex(-1);
  }, [value]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleKeyDown = (e) => {
    if (!showSuggestions || suggestions.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => (prev + 1) % suggestions.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => (prev - 1 + suggestions.length) % suggestions.length);
    } else if (e.key === 'Enter') {
      if (selectedIndex >= 0) {
        selectSuggestion(suggestions[selectedIndex]);
      }
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  };

  const selectSuggestion = (drug) => {
    onChange(drug.name);
    setShowSuggestions(false);
  };

  const highlightMatch = (text, query) => {
    if (!query) return text;
    const parts = text.split(new RegExp(`(${query})`, 'gi'));
    return (
      <span>
        {parts.map((part, i) => 
          part.toLowerCase() === query.toLowerCase() ? (
            <span key={i} className="text-blue-400 font-black">{part}</span>
          ) : (
            part
          )
        )}
      </span>
    );
  };

  return (
    <div className={`relative w-full ${showSuggestions ? 'z-50' : 'z-10'}`} ref={containerRef} onKeyDown={handleKeyDown}>
      <div className="space-y-3">
        <label className="text-[10px] font-black text-zinc-600 uppercase tracking-[0.3em] flex items-center gap-2">
          {Icon && <Icon size={12} className="text-blue-500"/>} Drug Selection
        </label>
        <div className="relative group">
          <input 
            className={`cyber-input w-full bg-white/[0.02] border-white/5 focus:border-blue-500/50 text-xl font-bold tracking-tight pr-12 transition-all ${disabled ? 'opacity-50 grayscale' : ''}`} 
            placeholder={placeholder}
            value={value}
            onChange={(e) => {
              onChange(e.target.value);
              setShowSuggestions(true);
            }}
            onFocus={() => setShowSuggestions(true)}
            disabled={disabled}
          />
          <div className="absolute right-4 top-1/2 -translate-y-1/2 opacity-20 group-focus-within:opacity-100 transition-opacity">
            <Search size={18} className="text-blue-500" />
          </div>
        </div>
      </div>

      <AnimatePresence>
        {showSuggestions && (
          <motion.div 
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            className="absolute z-[1000] w-full mt-2 glass-panel border border-white/10 overflow-hidden shadow-2xl overflow-y-auto max-h-[400px] custom-scrollbar"
          >
            {suggestions.length > 0 ? (
              <div className="flex flex-col">
                <div className="px-5 py-2 bg-white/[0.02] border-b border-white/5 text-[9px] font-black text-zinc-500 uppercase tracking-widest">
                  Found {suggestions.length} matches
                </div>
                {suggestions.map((s, i) => (
                  <button
                    key={i}
                    className={`w-full text-left px-5 py-4 flex items-center justify-between transition-all border-b border-white/5 last:border-none ${
                      selectedIndex === i ? 'bg-blue-500/20 text-white pl-8' : 'hover:bg-white/[0.03] text-zinc-400'
                    }`}
                    onClick={() => selectSuggestion(s)}
                    onMouseEnter={() => setSelectedIndex(i)}
                  >
                    <div className="flex flex-col gap-0.5">
                      <span className="text-sm font-bold tracking-tight">
                        {highlightMatch(s.name, value)}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-[9px] font-black uppercase text-zinc-600 tracking-widest">{s.class}</span>
                        <div className="w-1 h-1 rounded-full bg-zinc-800" />
                        <span className="text-[9px] font-bold text-blue-500/40 uppercase tracking-tighter">{s.category}</span>
                      </div>
                    </div>
                    {selectedIndex === i && (
                      <CornerDownLeft size={14} className="text-blue-500 animate-pulse" />
                    )}
                  </button>
                ))}
              </div>
            ) : value.trim().length > 0 ? (
              <div className="px-5 py-10 text-center flex flex-col items-center gap-4">
                 <FlaskConical size={32} className="text-zinc-800" />
                 <p className="text-[10px] font-black uppercase text-zinc-600 tracking-[0.3em]">No medical records found</p>
              </div>
            ) : (
              <div className="p-6">
                 <p className="text-[9px] font-black text-zinc-600 uppercase tracking-widest mb-4">Popular Medications</p>
                 <div className="grid grid-cols-2 gap-2">
                    {["Aspirin", "Warfarin", "Lisinopril", "Metformin"].map(p => (
                      <button 
                        key={p} 
                        className="text-left text-xs font-bold text-zinc-500 hover:text-white px-3 py-2 rounded-lg bg-white/[0.02] border border-white/5 hover:border-blue-500/30 transition-all"
                        onClick={() => onChange(p)}
                      >
                        {p}
                      </button>
                    ))}
                 </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
