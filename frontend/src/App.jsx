import React, { useState, useEffect, useRef } from 'react';
import { Search, Trash2, Upload, Database, Loader2, ExternalLink, FileText, X, Mic, Square, CheckCircle2, FileVideo, FileQuestion, Music } from 'lucide-react';

const API_BASE = "http://localhost:8000/api/v1";

export default function MultimodalRAG() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState(null);
  const [vault, setVault] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  // Audio Recording States
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorder = useRef(null);
  const audioChunks = useRef([]);

  const [history, setHistory] = useState(() => {
    const saved = localStorage.getItem("search_history");
    return saved ? JSON.parse(saved) : [];
  });

  const fetchVault = () => {
    fetch(`${API_BASE}/discovery/files`)
      .then(res => res.json())
      .then(data => { if (Array.isArray(data)) setVault(data); });
  };

  useEffect(() => { fetchVault(); }, []);

  const addToHistory = (queryText) => {
    const newHistory = [queryText, ...history.filter(h => h !== queryText)].slice(0, 10);
    setHistory(newHistory);
    localStorage.setItem("search_history", JSON.stringify(newHistory));
  };

  const handleSearch = async (e, forcedQuery) => {
    if (e) e.preventDefault();
    const activeQuery = forcedQuery || query;
    if (!activeQuery.trim()) return;

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/discovery/search?q=${encodeURIComponent(activeQuery)}`);
      const data = await res.json();
      setResult(data);
      addToHistory(activeQuery);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    setIsUploading(true);
    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("description", `Uploaded ${selectedFile.name}`);

    try {
      const response = await fetch(`${API_BASE}/ingestion/upload`, {
        method: "POST",
        body: formData
      });

      if (response.ok) {
        setSelectedFile(null);
        fetchVault();
        setShowSuccess(true);
        setTimeout(() => setShowSuccess(false), 3000);
      }
    } finally { setIsUploading(false); }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder.current = new MediaRecorder(stream);
      audioChunks.current = [];
      mediaRecorder.current.ondataavailable = (e) => audioChunks.current.push(e.data);

      mediaRecorder.current.onstop = async () => {
        const audioBlob = new Blob(audioChunks.current, { type: 'audio/wav' });
        const formData = new FormData();
        formData.append("file", audioBlob, "query.wav");

        setLoading(true);
        try {
          const res = await fetch(`${API_BASE}/discovery/search_audio`, {
            method: 'POST',
            body: formData
          });

          const data = await res.json();
          setResult(data);
          setQuery("Audio Search Results");
        } catch (err) { console.error(err); }
        finally { setLoading(false); }
      };

      mediaRecorder.current.start();
      setIsRecording(true);
    } catch (err) { alert("Mic access denied."); }
  };

  const stopRecording = () => {
    if (mediaRecorder.current && isRecording) {
      mediaRecorder.current.stop();
      setIsRecording(false);
    }
  };

  const handleDelete = async (filename) => {
    if (!window.confirm(`Delete ${filename}?`)) return;
    try {
      await fetch(`${API_BASE}/discovery/delete/${filename}`, { method: 'DELETE' });
      fetchVault();
      if (result) setResult(null);
    } catch (err) { console.error(err); }
  };

  // Logic to switch between search results and the full vault
  const displayItems = (query.trim() !== "" && result && result.sources?.length > 0) ? result.sources : vault;

  const renderPreview = (item) => {
    const fileName = item.filename || item.url.split('/').pop();
    const ext = fileName.split('.').pop().toLowerCase();
    const fileUrl = `http://localhost:8000/raw_uploads/${fileName}`;

    if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) {
      return <img src={fileUrl} className="w-full h-full object-cover" alt="preview" />;
    } else if (ext === 'pdf') {
      return <div className="flex flex-col items-center gap-2"><FileText size={40} className="text-cyan-500" /> <span className="text-[10px]">PDF Document</span></div>;
    } else if (['mp3', 'wav', 'ogg'].includes(ext)) {
      return (
        <div className="flex flex-col items-center gap-2">
          <Music size={40} className="text-pink-500" />
          <span className="text-[10px] text-pink-400 font-bold">Audio Track</span>
          <audio controls className="h-8 w-48 mt-2">
            <source src={fileUrl} type={`audio/${ext}`} />
          </audio>
        </div>
      );
    } else {
      return <div className="flex flex-col items-center gap-2"><FileQuestion size={40} className="text-slate-500" /> <span className="text-[10px] uppercase">{ext} File</span></div>;
    }
  };

  return (
    <div className="min-h-screen bg-[#0b0f1a] text-white p-6 font-sans">
      {showSuccess && (
        <div className="fixed top-6 right-6 bg-cyan-500 text-white px-6 py-3 rounded-2xl shadow-2xl flex items-center gap-3 z-50">
          <CheckCircle2 size={20} />
          <span className="font-bold text-sm">Media Indexed Successfully!</span>
        </div>
      )}

      <div className="max-w-7xl mx-auto flex items-center justify-between mb-8 border-b border-slate-800 pb-6">
        <div className="flex items-center gap-4">
          <div className="bg-cyan-500 p-2.5 rounded-xl"><Database size={24} /></div>
          <h1 className="text-2xl font-bold">Multimodal Engine</h1>
        </div>
      </div>

      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8 mb-8">
        {/* RECENTS */}
        <div className="lg:col-span-2 bg-[#161b2c] p-6 rounded-3xl border border-slate-800 h-fit">
          <h3 className="text-[10px] font-bold text-slate-500 uppercase mb-4">Recents</h3>
          <div className="space-y-1">
            {history.map((item, i) => (
              <button key={i} onClick={() => { setQuery(item); handleSearch(null, item); }} className="w-full text-left text-[11px] text-slate-400 hover:text-cyan-400 p-2 rounded-lg truncate transition-colors">
                {item}
              </button>
            ))}
          </div>
        </div>

        {/* SEARCH */}
        <div className="lg:col-span-7 bg-[#161b2c] p-8 rounded-3xl border border-slate-800">
          <form onSubmit={handleSearch} className="relative flex gap-3">
            <div className="relative flex-1">
              <input
                className="w-full bg-[#0b0f1a] border border-slate-700 rounded-xl py-4 px-6 outline-none focus:border-cyan-500"
                placeholder="Find 'flowers' or hum a song..."
                value={query}
                onChange={(e) => {
                   setQuery(e.target.value);
                   if(e.target.value === "") setResult(null);
                }}
              />
              <div className="absolute right-4 top-3 flex gap-2">
                {query && <button type="button" onClick={() => {setQuery(""); setResult(null);}}><X size={18} /></button>}
                <button
                  type="button"
                  onClick={isRecording ? stopRecording : startRecording}
                  className={isRecording ? "text-red-500 animate-pulse" : "text-slate-400 hover:text-cyan-400 transition-colors"}
                >
                  {isRecording ? <Square size={18} fill="currentColor" /> : <Mic size={18} />}
                </button>
              </div>
            </div>
            <button type="submit" className="bg-cyan-600 px-8 rounded-xl font-bold hover:bg-cyan-500 transition-all">
               {loading ? <Loader2 className="animate-spin" /> : "Analyze"}
            </button>
          </form>
        </div>

        {/* UPLOAD */}
        <div className="lg:col-span-3 bg-[#161b2c] p-8 rounded-3xl border border-slate-800">
          <div className="relative border-2 border-dashed border-slate-700 rounded-2xl p-6 text-center group cursor-pointer hover:border-cyan-500/50">
            <Upload className="mx-auto text-slate-500 mb-2 group-hover:text-cyan-400" />
            <p className="text-[10px] text-slate-500 truncate">{selectedFile ? selectedFile.name : "Drop media here"}</p>
            <input type="file" onChange={(e) => setSelectedFile(e.target.files[0])} className="absolute inset-0 opacity-0 cursor-pointer" />
          </div>
          <button onClick={handleUpload} disabled={!selectedFile || isUploading} className="w-full mt-4 bg-slate-800 py-3 rounded-xl text-sm font-bold hover:bg-slate-700 disabled:opacity-50">
            {isUploading ? <Loader2 className="animate-spin" size={16} /> : "Push to Vault"}
          </button>
        </div>
      </div>

      {/* GRID */}
      <div className="max-w-7xl mx-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {displayItems.map((item, i) => {
           const fileName = item.filename || item.url.split('/').pop();
           const isPDF = fileName.toLowerCase().endsWith('.pdf');
           const isVideo = ['mp4', 'webm'].includes(fileName.split('.').pop().toLowerCase());

           let finalUrl = `http://localhost:8000/raw_uploads/${fileName}`;
           if (isPDF && item.page) finalUrl += `#page=${item.page}`;
           if (isVideo && item.start_time) finalUrl += `#t=${item.start_time}`;

           return (
            <div key={i} className="bg-[#161b2c] rounded-2xl overflow-hidden border border-slate-800 group transition-all hover:translate-y-[-4px]">
              <div className="aspect-video bg-black flex items-center justify-center relative">
                 {renderPreview(item)}
                 <div className="absolute inset-0 bg-black/70 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-4">
                    <a href={finalUrl} target="_blank" rel="noopener noreferrer" className="bg-cyan-600 p-2.5 rounded-full">
                      <ExternalLink size={18} />
                    </a>
                    <button onClick={() => handleDelete(fileName)} className="bg-red-500/20 p-2.5 rounded-full text-red-500 hover:bg-red-500 hover:text-white">
                      <Trash2 size={18} />
                    </button>
                 </div>
              </div>
              <div className="p-3 bg-[#1c2336] flex flex-col gap-1">
                 <p className="text-[10px] text-slate-400 truncate">{fileName}</p>
                 <div className="flex justify-between items-center">
                    <div className="flex gap-2">
                       {item.page && <span className="text-[9px] text-cyan-500">Page {item.page}</span>}
                       {item.start_time && <span className="text-[9px] text-purple-500">At {item.start_time}s</span>}
                    </div>
                    {item.confidence && <span className="text-[9px] text-cyan-400">{Math.round(item.confidence * 100)}%</span>}
                 </div>
              </div>
            </div>
           );
        })}
      </div>
    </div>
  );
}