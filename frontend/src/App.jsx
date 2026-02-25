import React, { useState, useEffect, useRef } from 'react';
import { Search, Trash2, Upload, Database, Loader2, ExternalLink, FileText, X, Mic, Square, CheckCircle2, FileVideo, FileQuestion, Music, Clock } from 'lucide-react';

const API_BASE = "http://localhost:8000/api/v1";

export default function MultimodalRAG() {
  // --- STATE ---
  const [query, setQuery] = useState("");
  const [result, setResult] = useState(null);
  const [vault, setVault] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadDescription, setUploadDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const [volume, setVolume] = useState(0);
  const [isRecording, setIsRecording] = useState(false);

  // --- REFS ---
  const mediaRecorder = useRef(null);
  const audioChunks = useRef([]); // Critical fix: previously caused ReferenceError
  const audioContextRef = useRef(null);
  const animationRef = useRef(null);

  const [history, setHistory] = useState(() => {
    const saved = localStorage.getItem("search_history");
    return saved ? JSON.parse(saved) : [];
  });

  // --- VAULT ACTIONS ---
  const fetchVault = () => {
    fetch(`${API_BASE}/discovery/files`)
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) setVault(data);
        else if (data && data.files) setVault(data.files);
      })
      .catch(err => console.error("Vault fetch error:", err));
  };

  useEffect(() => { fetchVault(); }, []);

  const handleDelete = async (fileName) => {
    if (!window.confirm(`Delete ${fileName}?`)) return;
    try {
      await fetch(`${API_BASE}/discovery/files/${fileName}`, { method: 'DELETE' });
      fetchVault();
    } catch (err) { console.error("Delete failed:", err); }
  };

  // --- SEARCH ACTIONS ---
  const addToHistory = (queryText) => {
    if (!queryText) return;
    const newHistory = [queryText, ...history.filter(h => h !== queryText)].slice(0, 10);
    setHistory(newHistory);
    localStorage.setItem("search_history", JSON.stringify(newHistory));
  };

  const removeFromHistory = (e, itemToRemove) => {
    e.stopPropagation();
    const updatedHistory = history.filter(item => item !== itemToRemove);
    setHistory(updatedHistory);
    localStorage.setItem("search_history", JSON.stringify(updatedHistory));
  };

  const handleSearch = async (e, forcedQuery) => {
    if (e) e.preventDefault();
    const activeQuery = forcedQuery || query;
    if (!activeQuery.trim()) return;

    setLoading(true);
    setIsFocused(false);
    try {
      const res = await fetch(`${API_BASE}/discovery/search?q=${encodeURIComponent(activeQuery)}`);
      const data = await res.json();
      setResult(data);
      addToHistory(activeQuery);
    } catch (err) {
      console.error("Search failed:", err);
    } finally {
      setLoading(false);
    }
  };

  // --- UPLOAD ACTIONS ---
  const handleUpload = async () => {
    if (!selectedFile) return;
    setIsUploading(true);
    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("description", uploadDescription || `Uploaded ${selectedFile.name}`);

    try {
      const response = await fetch(`${API_BASE}/ingestion/upload`, {
        method: "POST",
        body: formData
      });
      if (response.ok) {
        setSelectedFile(null);
        setUploadDescription("");
        fetchVault();
        setShowSuccess(true);
        setTimeout(() => setShowSuccess(false), 3000);
      }
    } finally { setIsUploading(false); }
  };

  // --- VOICE ACTIONS ---
  const stopRecording = () => {
    if (mediaRecorder.current && mediaRecorder.current.state !== "inactive") {
      mediaRecorder.current.stop();
      mediaRecorder.current.stream.getTracks().forEach(track => track.stop());
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    cancelAnimationFrame(animationRef.current);
    setIsRecording(false);
    setVolume(0);
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 44100, channelCount: 1, echoCancellation: true }
      });

      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      const audioContext = new AudioCtx();
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      const updateVolume = () => {
        if (!audioContextRef.current) return;
        analyser.getByteFrequencyData(dataArray);
        let max = Math.max(...dataArray);
        setVolume((max / 255) * 100);
        animationRef.current = requestAnimationFrame(updateVolume);
      };
      updateVolume();

      audioChunks.current = [];
      setIsRecording(true);

      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorder.current = recorder;

      recorder.ondataavailable = async (e) => {
        if (e.data.size > 0) {
          audioChunks.current.push(e.data);
          const blob = new Blob(audioChunks.current, { type: "audio/webm" });
          const formData = new FormData();
          formData.append("file", blob, "chunk.webm");

          try {
            const res = await fetch(`${API_BASE}/discovery/transcribe_chunk`, {
              method: 'POST',
              body: formData
            });
            const contentType = res.headers.get("content-type");
            if (contentType && contentType.indexOf("application/json") !== -1) {
               const data = await res.json();
               if (data && data.text) {
                   setQuery(data.text.trim());
               }
            } else {
                const textFallback = await res.text();
                console.warn("Server sent non-JSON response:", textFallback);
            }
          } catch (err) {
            console.error("Transcription error:", err);
          }
        }
      };
      recorder.start(3000); // 3-second slices
    } catch (err) {
      alert(`Mic Error: ${err.message}`);
    }
  };

  // --- DISPLAY LOGIC ---
  const isSearching = query.trim() !== "" && result && result.sources;
  const displayItems = isSearching ? result.sources : vault;

  const renderPreview = (item) => {
    const fileName = item.filename || item.url?.split('/').pop() || "";
    const ext = fileName.split('.').pop().toLowerCase();
    const fileUrl = `${API_BASE.replace('/api/v1', '')}/raw_uploads/${fileName}`;

    if (['mp4', 'webm', 'mov', 'avi'].includes(ext)) {
      return (
        <div className="relative w-full h-full">
          <video className="w-full h-full object-cover" preload="metadata" muted>
            <source src={`${fileUrl}#t=0.5`} type={`video/${ext}`} />
          </video>
          <div className="absolute top-2 left-2 bg-black/60 p-1.5 rounded-lg"><FileVideo size={16} className="text-purple-400" /></div>
        </div>
      );
    }
    if (['mp3', 'wav', 'ogg'].includes(ext)) return <div className="flex flex-col items-center justify-center w-full h-full bg-[#1c2336]"><Music size={40} className="text-pink-500 animate-pulse" /></div>;
    if (['jpg', 'jpeg', 'png', 'webp'].includes(ext)) return <img src={fileUrl} className="w-full h-full object-cover" alt="preview" />;
    if (ext === 'pdf') return <div className="flex flex-col items-center justify-center h-full bg-slate-900"><FileText size={40} className="text-cyan-500" /></div>;
    return <FileQuestion size={40} className="text-slate-500" />;
  };

  return (
    <div className="min-h-screen bg-[#0b0f1a] text-white p-6 font-sans">
      <style>{`
        @keyframes pulse-cyan {
          0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(6, 182, 212, 0.7); }
          70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(6, 182, 212, 0); }
          100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(6, 182, 212, 0); }
        }
        .animate-pulse-cyan { animation: pulse-cyan 2s infinite; }
      `}</style>

      {/* HEADER */}
      <div className="max-w-7xl mx-auto flex items-center justify-between mb-8 border-b border-slate-800 pb-6">
        <div className="flex items-center gap-4">
          <div className="bg-cyan-500 p-2.5 rounded-xl"><Database size={24} /></div>
          <h1 className="text-2xl font-bold tracking-tight">Multimodal Engine</h1>
        </div>
        {showSuccess && <div className="flex items-center gap-2 text-cyan-400 text-sm font-bold animate-bounce"><CheckCircle2 size={16}/> File Ready!</div>}
      </div>

      {/* SEARCH + UPLOAD */}
      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8 mb-8">
        <div className="lg:col-span-9 bg-[#161b2c] p-8 rounded-3xl border border-slate-800 relative">
          <form onSubmit={handleSearch} className="relative flex gap-3">
            <div className="relative flex-1">
              {isRecording && (
                <div className="absolute -top-10 left-0 flex items-center gap-3">
                  <div className="flex items-end gap-1 h-4">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <div key={i} className="w-1 bg-cyan-400 rounded-full transition-all duration-75" style={{ height: `${Math.max(20, volume * (i * 0.4))}%` }}></div>
                    ))}
                  </div>
                  <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-widest">Voice Active...</span>
                </div>
              )}
              <input
                className={`w-full bg-[#0b0f1a] border rounded-xl py-4 px-6 outline-none transition-all ${isRecording ? "border-cyan-500" : "border-slate-700 focus:border-cyan-500"}`}
                placeholder="Search your vault..."
                value={query}
                onFocus={() => setIsFocused(true)}
                onBlur={() => setTimeout(() => setIsFocused(false), 200)}
                onChange={(e) => { setQuery(e.target.value); if(e.target.value === "") setResult(null); }}
              />

              {isFocused && history.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-2 bg-[#1c2336] border border-slate-700 rounded-2xl shadow-2xl z-[100] overflow-hidden">
                  {history.map((text, i) => (
                    <div key={i} className="flex items-center hover:bg-slate-800 group">
                      <button type="button" onMouseDown={() => { setQuery(text); handleSearch(null, text); }} className="flex-1 flex items-center gap-3 px-6 py-3 text-left text-sm text-slate-300">
                        <Clock size={14} className="text-slate-500" /> {text}
                      </button>
                      <button onMouseDown={(e) => removeFromHistory(e, text)} className="p-3 text-slate-500 hover:text-red-400 opacity-0 group-hover:opacity-100"><X size={14} /></button>
                    </div>
                  ))}
                </div>
              )}

              <div className="absolute right-4 top-3 flex gap-2">
                {query && <button type="button" onClick={() => {setQuery(""); setResult(null);}} className="p-2 text-slate-500"><X size={18} /></button>}
                <button type="button" onClick={isRecording ? stopRecording : startRecording} className={`p-2 rounded-full transition-all ${isRecording ? "bg-red-500 text-white animate-pulse-cyan" : "text-slate-400 hover:text-cyan-400"}`}>
                  {isRecording ? <Square size={18} fill="currentColor" /> : <Mic size={18} />}
                </button>
              </div>
            </div>
            <button type="submit" className="bg-cyan-600 px-8 rounded-xl font-bold h-[58px] hover:bg-cyan-500 transition-colors">{loading ? <Loader2 className="animate-spin" /> : "Analyze"}</button>
          </form>
        </div>

        <div className="lg:col-span-3 bg-[#161b2c] p-6 rounded-3xl border border-slate-800">
          <div className="relative border-2 border-dashed border-slate-700 rounded-2xl p-4 text-center group cursor-pointer hover:border-cyan-500/50">
            <Upload className="mx-auto text-slate-500 mb-2 group-hover:text-cyan-400" size={20} />
            <p className="text-[10px] text-slate-500 truncate">{selectedFile ? selectedFile.name : "Upload Media"}</p>
            <input type="file" onChange={(e) => setSelectedFile(e.target.files[0])} className="absolute inset-0 opacity-0 cursor-pointer" />
          </div>
          <textarea className="w-full mt-3 bg-[#0b0f1a] border border-slate-700 rounded-xl p-3 text-[11px] min-h-[60px]" placeholder="Add context..." value={uploadDescription} onChange={(e) => setUploadDescription(e.target.value)} />
          <button onClick={handleUpload} disabled={!selectedFile || isUploading} className="w-full mt-3 bg-slate-800 hover:bg-slate-700 py-3 rounded-xl text-sm font-bold disabled:opacity-50">
            {isUploading ? <Loader2 className="animate-spin mx-auto" size={16} /> : "Push to Vault"}
          </button>
        </div>
      </div>

      {/* MEDIA GRID */}
      <div className="max-w-7xl mx-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {displayItems.length > 0 ? displayItems.map((item, i) => {
           const fileName = item.filename || item.url?.split('/').pop() || "file";
           const isPDF = fileName.toLowerCase().endsWith('.pdf');
           const isVideo = ['mp4', 'webm', 'mov'].includes(fileName.split('.').pop().toLowerCase());
           let finalUrl = `${API_BASE.replace('/api/v1', '')}/raw_uploads/${fileName}`;
           if (isPDF && (item.page || item.page_number)) finalUrl += `#page=${item.page || item.page_number}`;
           if (isVideo && (item.timestamp || item.start_time)) finalUrl += `#t=${item.timestamp || item.start_time}`;

           return (
            <div key={i} className="bg-[#161b2c] rounded-2xl overflow-hidden border border-slate-800 group hover:scale-[1.02] transition-transform">
              <div className="aspect-video bg-black flex items-center justify-center relative">
                 {renderPreview(item)}
                 <div className="absolute inset-0 bg-black/70 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-4">
                    <a href={finalUrl} target="_blank" rel="noopener noreferrer" className="bg-cyan-600 p-2.5 rounded-full hover:bg-cyan-500"><ExternalLink size={18} /></a>
                    <button onClick={() => handleDelete(fileName)} className="bg-red-500/20 p-2.5 rounded-full text-red-500 hover:bg-red-500 hover:text-white"><Trash2 size={18} /></button>
                 </div>
              </div>
              <div className="p-3 bg-[#1c2336]">
                 <p className="text-[10px] text-slate-400 truncate">{fileName}</p>
                 <div className="flex justify-between items-center mt-1">
                   <div className="flex gap-2">
                      {(item.page || item.page_number) && <span className="text-[9px] text-cyan-500 font-bold uppercase">Page {item.page || item.page_number}</span>}
                      {(item.timestamp || item.start_time) && <span className="text-[9px] text-purple-500 font-bold uppercase">At {item.timestamp || item.start_time}s</span>}
                   </div>
                   {item.similarity && <span className="text-[9px] text-slate-500 uppercase">{Math.round(item.similarity * 100)}% Match</span>}
                 </div>
              </div>
            </div>
           );
        }) : (
          <div className="col-span-full py-20 text-center text-slate-500 border-2 border-dashed border-slate-800 rounded-3xl bg-[#161b2c]">
            No media found in vault. Start uploading!
          </div>
        )}
      </div>
    </div>
  );
}