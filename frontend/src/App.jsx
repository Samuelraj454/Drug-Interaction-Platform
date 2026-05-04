import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Search, 
  History as HistoryIcon, 
  Activity, 
  AlertTriangle, 
  ShieldCheck, 
  Clock, 
  ChevronRight,
  TrendingUp,
  Cpu,
  Zap,
  LayoutDashboard,
  LogOut,
  Database,
  BarChart3,
  Server,
  FlaskConical
} from 'lucide-react';
import { analyzeInteraction, fetchHistory, fetchSystemStats } from './services/apiService';
import DrugSearchInput from './components/DrugSearchInput';

// --- Constants ---
const SEVERITY_COLORS = {
  None: "text-emerald-400 neon-text-green",
  Mild: "text-blue-400 neon-text-blue",
  Moderate: "text-amber-500 neon-text-amber",
  Severe: "text-orange-500 neon-text-orange",
  Contraindicated: "text-red-500 animate-pulse neon-text-red",
  Unknown: "text-zinc-600"
};

const SEVERITY_GLOW = {
  None: "0 0 20px rgba(16, 185, 129, 0.3)",
  Mild: "0 0 20px rgba(59, 130, 246, 0.3)",
  Moderate: "0 0 20px rgba(245, 158, 11, 0.3)",
  Severe: "0 0 20px rgba(249, 115, 22, 0.3)",
  Contraindicated: "0 0 40px rgba(239, 68, 68, 0.6)",
};

const SEVERITY_BG = {
  None: "bg-emerald-500/10 border-emerald-500/20",
  Mild: "bg-blue-500/10 border-blue-500/20",
  Moderate: "bg-yellow-500/10 border-yellow-500/20",
  Severe: "bg-red-500/10 border-red-500/20",
  Contraindicated: "bg-red-950 border-red-500",
  Unknown: "bg-zinc-900 border-zinc-800"
};

// --- Main App Component ---
export default function App() {
  const [activeTab, setActiveTab] = useState(() => {
    return localStorage.getItem('active_rx_tab') || 'analyzer';
  });
  const [drugA, setDrugA] = useState('');
  const [drugB, setDrugB] = useState('');
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  
  // Results
  const [severity, setSeverity] = useState(null);
  const [confidence, setConfidence] = useState(0);
  const [explanation, setExplanation] = useState('');
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [history, setHistory] = useState(() => {
    try {
      const saved = localStorage.getItem('drug_interaction_history');
      return saved ? JSON.parse(saved) : [];
    } catch (e) {
      return [];
    }
  });
  const [stats, setStats] = useState({
    total_interactions: 0,
    avg_latency_ms: 0,
    llm_ttft_sec: 0,
    success_rate: 100,
    requests_per_hr: 0
  });

  // Auto-scroll explanation
  const explanationEndRef = useRef(null);
  useEffect(() => {
    if (explanationEndRef.current) {
      explanationEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [explanation]);

  // Refresh System Stats
  const refreshStats = async () => {
    const data = await fetchSystemStats();
    if (data) setStats(data);
  };

  useEffect(() => {
    localStorage.setItem('active_rx_tab', activeTab);
  }, [activeTab]);

  useEffect(() => {
    refreshStats();
    const interval = setInterval(refreshStats, 10000); // Poll every 10s
    return () => clearInterval(interval);
  }, []);

  // Sync History to LocalStorage
  useEffect(() => {
    localStorage.setItem('drug_interaction_history', JSON.stringify(history));
  }, [history]);

  // Save History
  const saveToHistory = (entry) => {
    setHistory(prevHistory => {
      const filtered = prevHistory.filter(h => !(h.drug_a === entry.drug_a && h.drug_b === entry.drug_b));
      return [entry, ...filtered].slice(0, 10);
    });
  };

  const [clinicalData, setClinicalData] = useState(null);

  const handleSearch = async () => {
    if (!drugA.trim() || !drugB.trim()) return;
    
    // Reset state
    setLoading(true);
    setStreaming(false);
    setErrorMsg(null);
    setSeverity(null);
    setClinicalData(null);
    setExplanation('');
    setFeedbackSubmitted(false);
    
    await analyzeInteraction(
      drugA, 
      drugB, 
      (event) => {
        setLoading(false);
        if (event.event === 'clinical_data') {
          setClinicalData(event.data);
          setSeverity(event.data.severity);
          setConfidence(event.data.confidence);
          saveToHistory({
            drug_a: drugA,
            drug_b: drugB,
            severity: event.data.severity,
            timestamp: new Date().toISOString()
          });
        } else if (event.event === 'severity' && !clinicalData) {
          setSeverity(event.severity);
          setConfidence(event.confidence);
          saveToHistory({
            drug_a: drugA,
            drug_b: drugB,
            severity: event.severity,
            timestamp: new Date().toISOString()
          });
        } else if (event.event === 'token') {
          setStreaming(true);
          setExplanation(prev => prev + event.text);
        } else if (event.event === 'error') {
          setErrorMsg(event.message);
          setStreaming(false);
        }
      },
      (err) => {
        setLoading(false);
        setStreaming(false);
        setErrorMsg(err);
      }
    );

    setStreaming(false);
  };

  const loadFromHistory = (item) => {
    setDrugA(item.drug_a);
    setDrugB(item.drug_b);
    setActiveTab('analyzer');
  };

  return (
    <div className="flex h-screen overflow-hidden text-zinc-400 bg-[#020204] selection:bg-blue-500/30 font-inter">
      {/* Premium Dynamic Mesh Background */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <div className="mesh-gradient opacity-40" />
        <div className="particle-bg" />
        <motion.div 
          animate={{ 
            x: [0, 100, -50, 0], 
            y: [0, -50, 100, 0],
          }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
          className="absolute -top-[10%] -left-[10%] w-[60vw] h-[60vw] rounded-full bg-blue-600/10 blur-[120px] mix-blend-screen" 
        />
        <motion.div 
          animate={{ 
            x: [0, -100, 50, 0], 
            y: [0, 100, -50, 0],
          }}
          transition={{ duration: 25, repeat: Infinity, ease: "linear" }}
          className="absolute top-[20%] -right-[10%] w-[50vw] h-[50vw] rounded-full bg-emerald-600/10 blur-[120px] mix-blend-screen" 
        />
      </div>

      {/* Glass Sidebar */}
      <nav className="w-20 lg:w-72 bg-black/60 backdrop-blur-3xl border-r border-white/[0.05] flex flex-col p-4 z-50">
        <div className="flex items-center gap-4 px-3 py-8 mb-10">
          <motion.div 
            whileHover={{ scale: 1.05, rotate: 5 }}
            className="w-12 h-12 bg-gradient-to-br from-blue-600 to-indigo-700 rounded-xl flex items-center justify-center shadow-[0_0_20px_rgba(37,99,235,0.4)]"
          >
            <ShieldCheck className="text-white" size={26} />
          </motion.div>
          <div className="hidden lg:block">
            <h1 className="font-outfit font-black text-2xl text-white tracking-tight leading-none uppercase tracking-widest">AETHER<span className="text-blue-500">AI</span></h1>
            <p className="text-[9px] font-black text-blue-500/50 tracking-[0.4em] uppercase mt-1">Clinical Decision Core</p>
          </div>
        </div>

        <div className="flex flex-col gap-1.5 flex-grow">
          <NavItem 
            icon={<Search size={20} />} 
            label="Neural Scan" 
            active={activeTab === 'analyzer'} 
            onClick={() => setActiveTab('analyzer')} 
          />
          <NavItem 
            icon={<HistoryIcon size={20} />} 
            label="Case History" 
            active={activeTab === 'history'} 
            onClick={() => setActiveTab('history')} 
          />
          <NavItem 
            icon={<LayoutDashboard size={20} />} 
            label="Intelligence Hub" 
            active={activeTab === 'dashboard'} 
            onClick={() => setActiveTab('dashboard')} 
          />
        </div>

        <div className="mt-auto pt-6 border-t border-white/[0.05]">
          <button className="flex items-center gap-4 px-4 py-3 rounded-xl text-zinc-600 hover:text-white hover:bg-white/5 transition-all w-full">
            <LogOut size={18} />
            <span className="hidden lg:block font-black text-[10px] uppercase tracking-[0.2em]">Logout</span>
          </button>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="flex-grow flex flex-col relative z-10 overflow-hidden">
        <header className="h-20 border-b border-white/[0.05] flex items-center justify-between px-10 bg-black/40 backdrop-blur-xl">
           <div className="flex flex-col gap-1">
             <h2 className="text-[10px] font-black text-zinc-500 uppercase tracking-[0.4em]">{activeTab}</h2>
             <div className="flex items-center gap-2">
               <div className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_8px_#3b82f6]" />
               <span className="text-xs font-bold text-white tracking-widest uppercase">SYST_ON_CORE</span>
             </div>
           </div>
           
           {severity && (
             <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="flex items-center gap-4 bg-white/[0.02] border border-white/5 px-6 py-2 rounded-full">
               <span className="text-[10px] font-black uppercase tracking-[0.3em] text-zinc-500">{drugA}</span>
               <div className="w-8 h-[1px] bg-zinc-800" />
               <Zap size={14} className="text-blue-500"/>
               <div className="w-8 h-[1px] bg-zinc-800" />
               <span className="text-[10px] font-black uppercase tracking-[0.3em] text-zinc-500">{drugB}</span>
             </motion.div>
           )}

           <div className="flex items-center gap-8">
              <div className="w-10 h-10 rounded-xl bg-white/[0.03] border border-white/[0.05] flex items-center justify-center group hover:border-blue-500/30 transition-colors">
                 <Server size={18} className="text-blue-500 group-hover:scale-110 transition-transform"/>
              </div>
           </div>
        </header>

        <section className="flex-grow overflow-y-auto p-4 lg:p-10 scrollbar-hide">
          <AnimatePresence mode="wait">
            {activeTab === 'analyzer' && (
              <motion.div 
                key="analyzer"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="max-w-[1600px] mx-auto h-full flex flex-col gap-8"
              >
                 {/* Top Search Area */}
                 <div className="glass-panel p-8 relative group">
                    <div className={`scanning-overlay ${loading ? 'active' : ''}`}>
                      <div className="scan-line" />
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-end relative z-10">
                      <div className="md:col-span-4">
                         <DrugSearchInput value={drugA} onChange={setDrugA} placeholder="Input Agent 1..." disabled={loading} icon={FlaskConical} />
                      </div>
                      <div className="md:col-span-1 flex items-center justify-center pb-5">
                        <Zap size={16} className="text-blue-500/40"/>
                      </div>
                      <div className="md:col-span-4">
                         <DrugSearchInput value={drugB} onChange={setDrugB} placeholder="Input Agent 2..." disabled={loading} icon={FlaskConical} />
                      </div>
                      <div className="md:col-span-3">
                        <button 
                          className="cyber-btn w-full h-[56px] text-[10px] font-black uppercase tracking-[0.3em] bg-blue-600 hover:bg-blue-500 border-none shadow-[0_0_30px_rgba(37,99,235,0.2)]"
                          onClick={handleSearch}
                          disabled={loading || !drugA || !drugB}
                        >
                           {loading ? <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin"/> : "INITIATE_NEURAL_SCAN"}
                        </button>
                      </div>
                    </div>
                 </div>

                 <div className="flex-grow grid grid-cols-1 lg:grid-cols-12 gap-8 min-h-0">
                    {/* Left: Search Status / History (Implicitly handled by UI state) */}
                    <div className="lg:col-span-3 flex flex-col gap-6">
                       <div className="glass-panel p-6 flex flex-col gap-6">
                          <p className="text-[10px] font-black text-zinc-600 uppercase tracking-[0.4em]">System Status</p>
                          <div className="space-y-4">
                             <StatusRow label="Connection" value="Secure" active />
                             <StatusRow label="Reasoning" value={loading || streaming ? "Active" : "Idle"} active={loading || streaming} />
                             <StatusRow label="Expert Core" value="Online" active />
                          </div>
                          
                          <div className="mt-6 pt-6 border-t border-white/5">
                             <p className="text-[10px] font-black text-zinc-600 uppercase tracking-[0.4em] mb-4">Neural Buffer</p>
                             <div className="flex flex-col gap-2">
                                {history.slice(0, 3).map((h, i) => (
                                  <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/5 hover:bg-white/5 transition-colors cursor-pointer" onClick={() => loadFromHistory(h)}>
                                     <div className={`w-1.5 h-1.5 rounded-full ${SEVERITY_COLORS[h.severity]?.split(' ')[0].replace('text-', 'bg-')}`} />
                                     <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-tight">{h.drug_a} + {h.drug_b}</span>
                                  </div>
                                ))}
                             </div>
                          </div>
                       </div>
                    </div>

                    {/* Center: Severity & Explanation */}
                    <div className="lg:col-span-5 flex flex-col gap-8">
                       <div className="glass-panel flex-grow flex flex-col items-center justify-center p-10 relative overflow-hidden">
                          {severity ? (
                            <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="flex flex-col items-center gap-10 w-full relative z-10">
                               <div className="text-center space-y-2">
                                  <p className="text-[10px] font-black text-zinc-600 uppercase tracking-[0.5em]">Clinical Interaction Severity</p>
                                  <h3 className={`text-7xl font-black uppercase tracking-tighter ${SEVERITY_COLORS[severity]} glow-severe risk-pulse`}>
                                     {severity}
                                  </h3>
                               </div>

                               <div className="w-64 h-64 relative flex items-center justify-center">
                                  <div className={`absolute inset-0 rounded-full blur-[80px] opacity-20 ${severity === 'Severe' || severity === 'Contraindicated' ? 'bg-red-500' : 'bg-blue-500'}`} />
                                  <div className="severity-orb w-48 h-48 z-10 glass-panel !rounded-full flex flex-col items-center justify-center border-white/10">
                                     <Activity size={48} className={`${SEVERITY_COLORS[severity]} mb-2`}/>
                                     <span className="text-2xl font-black text-white">{(confidence * 100).toFixed(0)}%</span>
                                     <span className="text-[8px] font-black text-zinc-500 uppercase tracking-widest">Confidence</span>
                                  </div>
                                  <motion.div animate={{ rotate: 360 }} transition={{ duration: 10, repeat: Infinity, ease: "linear" }} className="absolute inset-0 border border-white/5 border-t-blue-500/30 rounded-full" />
                               </div>

                               <div className="w-full max-w-sm space-y-4">
                                  <div className="severity-bar-gradient">
                                     <div className="severity-indicator-dot" style={{ left: severity === 'None' ? '10%' : severity === 'Mild' ? '30%' : severity === 'Moderate' ? '50%' : severity === 'Severe' ? '80%' : '95%' }} />
                                  </div>
                                  <div className="flex justify-between text-[8px] font-black text-zinc-700 uppercase tracking-widest">
                                     <span>Negligible</span>
                                     <span>Extreme Risk</span>
                                  </div>
                               </div>
                            </motion.div>
                          ) : (
                            <div className="flex flex-col items-center gap-8 opacity-20">
                               <ShieldCheck size={120} strokeWidth={0.5} className="text-white/20"/>
                               <p className="text-[11px] font-black uppercase tracking-[0.6em]">System Standby</p>
                            </div>
                          )}
                       </div>

                       <div className="glass-panel p-8 h-48 overflow-y-auto custom-scrollbar">
                          <p className="text-[9px] font-black text-zinc-600 uppercase tracking-[0.4em] mb-4 flex items-center gap-2">
                             <Cpu size={12}/> Neural Reasoning Output
                          </p>
                          <div className="text-xs font-medium leading-relaxed text-zinc-400 whitespace-pre-wrap">
                             {explanation || "Awaiting scan initiation..."}
                             {streaming && <span className="streaming-cursor"/>}
                          </div>
                       </div>
                    </div>

                    {/* Right: Clinical Insight Panel */}
                    <div className="lg:col-span-4 flex flex-col gap-6">
                       <div className="glass-panel flex-grow flex flex-col overflow-hidden">
                          <div className="px-8 py-5 border-b border-white/5 bg-white/[0.02] flex items-center justify-between">
                             <p className="text-[10px] font-black text-white uppercase tracking-[0.3em] flex items-center gap-2">
                                <Activity size={14} className="text-blue-500"/>
                                Clinical Insight Panel
                             </p>
                             <div className="px-2 py-1 bg-blue-500/10 border border-blue-500/20 rounded text-[8px] font-black text-blue-400 uppercase tracking-widest">Expert Core v4.0</div>
                          </div>
                          
                          <div className="flex-grow overflow-y-auto p-2 scrollbar-hide">
                             {clinicalData ? (
                                <div className="flex flex-col h-full">
                                   <InsightField label="Interaction Type" value={clinicalData.type} icon={<Zap size={14}/>} />
                                   <InsightField label="Mechanism of Action" value={clinicalData.mechanism[0]} icon={<Activity size={14}/>} />
                                   <InsightField label="Clinical Risk" value={clinicalData.risk} icon={<AlertTriangle size={14}/>} color="text-red-400" />
                                   <InsightField label="Evidence Level" value={clinicalData.evidence} icon={<Database size={14}/>} />
                                   <InsightField label="Neural Confidence" value={`${(clinicalData.confidence * 100).toFixed(1)}%`} icon={<Cpu size={14}/>} />
                                   
                                   <div className="p-6 mt-4">
                                      <p className="insight-label mb-3">Expert Reasoning</p>
                                      <p className="text-xs font-medium text-zinc-400 leading-loose italic">"{clinicalData.why}"</p>
                                   </div>

                                   <div className="p-6 mt-auto border-t border-white/5 bg-blue-500/5">
                                      <p className="insight-label text-blue-400 mb-4 flex items-center gap-2"><TrendingUp size={12}/> Actionable Recommendation</p>
                                      <p className="text-xs font-bold text-white leading-relaxed">{clinicalData.recommendation}</p>
                                   </div>
                                </div>
                             ) : (
                                <div className="h-full flex flex-col items-center justify-center p-10 opacity-20 text-center gap-4">
                                   <Database size={60} strokeWidth={0.5}/>
                                   <p className="text-[10px] font-black uppercase tracking-[0.4em]">Structured insight data will populate here after scan</p>
                                </div>
                             )}
                          </div>
                       </div>

                       {/* Actionable Buttons */}
                       <div className="grid grid-cols-2 gap-4">
                          <ActionButton icon={<AlertTriangle size={14}/>} label="View Guidelines" />
                          <ActionButton icon={<Activity size={14}/>} label="Alternatives" />
                       </div>
                    </div>
                 </div>
              </motion.div>
            )}

            {/* History and Dashboard tabs remain mostly same but themed */}
            {activeTab === 'history' && (
              <motion.div key="history" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="max-w-6xl mx-auto flex flex-col gap-6">
                 <div className="glass-panel overflow-hidden">
                    <table className="w-full text-left border-collapse">
                       <thead className="bg-white/[0.02] border-b border-white/5 text-[9px] font-black text-zinc-600 uppercase tracking-[0.4em]">
                          <tr>
                             <th className="px-10 py-6">Interaction Pair</th>
                             <th className="px-10 py-6">Haz_Level</th>
                             <th className="px-10 py-6">Audit_Timestamp</th>
                             <th className="px-10 py-6 text-right">Recall</th>
                          </tr>
                       </thead>
                       <tbody className="divide-y divide-white/5 font-bold">
                          {history.length > 0 ? history.map((item, i) => (
                             <motion.tr 
                               initial={{ opacity: 0, x: -10 }}
                               animate={{ opacity: 1, x: 0 }}
                               transition={{ delay: i * 0.05 }}
                               key={i} 
                               className="hover:bg-blue-500/[0.03] transition-colors group"
                             >
                                <td className="px-10 py-8">
                                   <div className="flex items-center gap-5">
                                      <div className="w-10 h-10 rounded-lg bg-zinc-900 border border-white/5 flex items-center justify-center text-[10px] font-black text-blue-500">PX</div>
                                      <div className="flex flex-col gap-0.5">
                                        <span className="text-sm font-black text-white uppercase tracking-tight">{item.drug_a}</span>
                                        <div className="flex items-center gap-1.5 overflow-hidden">
                                          <div className="w-4 h-[1px] bg-zinc-800" />
                                          <span className="text-[10px] text-zinc-600 uppercase tracking-widest">{item.drug_b}</span>
                                        </div>
                                      </div>
                                   </div>
                                </td>
                                <td className="px-10 py-8">
                                   <span className={`text-[9px] font-black px-3 py-1 rounded-sm border ${SEVERITY_BG[item.severity]} ${SEVERITY_COLORS[item.severity]} border-current/30 uppercase tracking-widest`}>
                                      {item.severity}
                                   </span>
                                </td>
                                <td className="px-10 py-8 text-[11px] text-zinc-600 font-mono">
                                   {new Date(item.timestamp).toISOString().split('T')[0]} {new Date(item.timestamp).toLocaleTimeString([], { hour12: false })}
                                 </td>
                                <td className="px-10 py-8 text-right">
                                   <button 
                                     onClick={() => loadFromHistory(item)}
                                     className="px-5 py-2 bg-white/[0.03] border border-white/5 rounded-lg text-[9px] font-black text-blue-500 hover:bg-blue-500 hover:text-white transition-all uppercase tracking-[0.2em] opacity-0 group-hover:opacity-100"
                                   >
                                      INSPECT_LOG
                                   </button>
                                </td>
                             </motion.tr>
                          )) : (
                             <tr><td colSpan="4" className="px-10 py-24 text-center text-zinc-800 font-black uppercase tracking-[0.5em]">No clinical logs found in archive.</td></tr>
                          )}
                       </tbody>
                    </table>
                 </div>
              </motion.div>
            )}

            {activeTab === 'dashboard' && (
              <motion.div key="dashboard" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="h-full flex flex-col gap-10">
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                    <StatCard icon={<ShieldCheck size={20} className="text-emerald-500"/>} label="Cluster Health" value={`${stats.success_rate}%`} subLabel="Uptime Verified" />
                    <StatCard icon={<Activity size={20} className="text-blue-500"/>} label="Mean Latency" value={`${stats.avg_latency_ms}ms`} subLabel="Response Floor" />
                    <StatCard icon={<Zap size={20} className="text-blue-400"/>} label="Response TTFT" value={`${stats.llm_ttft_sec}s`} subLabel="Neural Warmup" />
                    <StatCard icon={<Database size={20} className="text-zinc-600"/>} label="Total Assets" value={stats.total_interactions.toLocaleString()} subLabel="Clinical DB Size" />
                 </div>

                 {/* Live Telemetry View */}
                 <div className="flex-grow glass-panel bg-black flex flex-col relative min-h-[500px]">
                    <div className="p-6 border-b border-white/5 flex items-center justify-between bg-white/[0.01]">
                       <div className="flex items-center gap-3">
                         <Activity size={16} className="text-emerald-500 animate-pulse"/>
                         <span className="text-[10px] font-black text-zinc-500 uppercase tracking-[0.3em]">Real-Time Observability Core</span>
                       </div>
                    </div>
                    {/* Grafana Dashboard Iframe */}
                    <div className="flex-grow p-1">
                      <iframe 
                        src="http://localhost:3001/d/system-health/system-health?orgId=1&refresh=5s&theme=dark&kiosk" 
                        className="w-full h-full border-none rounded-xl grayscale-[0.2] opacity-90 hover:grayscale-0 transition-all"
                        title="Grafana Analytics"
                      />
                    </div>
                 </div>
              </motion.div>
            )}
          </AnimatePresence>
        </section>
      </main>
    </div>
  );
}

const NavItem = ({ icon, label, active, onClick }) => (
  <button 
    onClick={onClick}
    className={`flex items-center gap-4 px-4 py-4 rounded-xl transition-all duration-300 relative group w-full ${
      active 
        ? "text-blue-500 bg-blue-500/10 shadow-[0_0_15px_rgba(59,130,246,0.15)]" 
        : "text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.03]"
    }`}
  >
    {active && <motion.div layoutId="nav-glow" className="absolute left-0 w-1 h-6 bg-blue-500 rounded-full shadow-[0_0_10px_#3b82f6]" />}
    <span className="relative z-10 group-hover:scale-110 transition-transform">{icon}</span>
    <span className="hidden lg:block font-black text-[9px] uppercase tracking-[0.25em] relative z-10">{label}</span>
  </button>
);

const StatCard = ({ icon, label, value, subLabel }) => (
  <div className="glass-panel p-6 group hover:border-blue-500/30 transition-all duration-500">
    <div className="flex items-center justify-between mb-4">
      <div className="w-10 h-10 rounded-xl bg-white/[0.03] border border-white/5 flex items-center justify-center group-hover:scale-110 transition-transform">
        {icon}
      </div>
    </div>
    <div className="space-y-1">
      <p className="text-[9px] font-black text-zinc-600 uppercase tracking-[0.3em]">{label}</p>
      <p className="text-2xl font-black text-white tracking-tighter">{value}</p>
      <p className="text-[9px] font-bold text-zinc-500 uppercase tracking-widest mt-2">{subLabel}</p>
    </div>
  </div>
);

const StatusRow = ({ label, value, active }) => (
  <div className="flex items-center justify-between">
    <span className="text-[10px] font-bold text-zinc-600 uppercase tracking-widest">{label}</span>
    <div className="flex items-center gap-2">
       <span className={`text-[10px] font-black uppercase ${active ? 'text-blue-500' : 'text-zinc-800'}`}>{value}</span>
       <div className={`w-1.5 h-1.5 rounded-full ${active ? 'bg-blue-500 animate-pulse' : 'bg-zinc-800'}`} />
    </div>
  </div>
);

const InsightField = ({ label, value, icon, color = "text-white" }) => (
  <div className="insight-field group hover:bg-white/[0.01] transition-colors">
    <div className="flex items-center gap-2 mb-1 opacity-60">
       <div className="text-blue-500">{icon}</div>
       <p className="insight-label m-0">{label}</p>
    </div>
    <p className={`insight-value m-0 ${color}`}>{value}</p>
  </div>
);

const ActionButton = ({ icon, label }) => (
  <button className="glass-panel py-4 flex items-center justify-center gap-3 hover:bg-blue-500/10 hover:border-blue-500/30 transition-all group">
     <div className="text-blue-500 group-hover:scale-110 transition-transform">{icon}</div>
     <span className="text-[9px] font-black text-zinc-400 group-hover:text-white uppercase tracking-[0.2em]">{label}</span>
  </button>
);

