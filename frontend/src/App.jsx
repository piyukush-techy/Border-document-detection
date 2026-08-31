import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast, Toaster } from 'react-hot-toast';
import { Shield, Upload, Camera, FileText, BarChart3, Settings, Download, HelpCircle } from 'lucide-react';

import { useTheme } from './hooks/useTheme';
import { useApi } from './hooks/useApi';
import { dataUrlToBlob, verdictFromScore, formatTimestamp, truncateHash, cn } from './lib/utils';

import Button from './components/Button';
import { Card, CardHeader, CardContent, CardFooter } from './components/Card';
import Badge from './components/Badge';
import ThemeToggle from './components/ThemeToggle';
import ProgressBar from './components/ProgressBar';
import VerdictBanner from './components/VerdictBanner';

const DOC_TYPES = [
  { id: 'passport', label: 'Passport', icon: FileText },
  { id: 'visa', label: 'Visa', icon: FileText },
  { id: 'national_id', label: 'National ID', icon: Shield },
  { id: 'driving_license', label: 'Driving License', icon: FileText },
  { id: 'permit', label: 'Permit Document', icon: Shield },
];

const PROCESSING_STEPS = [
  'Extracting OCR text fields...',
  'Validating checksums and formats...',
  'Analyzing tampering artifacts...',
  'Executing face verification...',
  'Running liveness detection...',
  'Fusing scores and generating verdict...',
];

export default function App() {
  const { theme, toggleTheme } = useTheme();
  const { verifyDocument, checkHealth, getModulesStatus, getAuditLog, loading, error } = useApi();
  
  const [docType, setDocType] = useState('national_id');
  const [documentFile, setDocumentFile] = useState(null);
  const [selfieFile, setSelfieFile] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [results, setResults] = useState(null);
  const [auditLog, setAuditLog] = useState([]);
  const [backendOnline, setBackendOnline] = useState(null);
  const [modulesOk, setModulesOk] = useState(null);
  const [showHelp, setShowHelp] = useState(false);

  // --- Live selfie capture state ---
  const [selfieMode, setSelfieMode] = useState('upload'); // 'upload' | 'camera'
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState(null);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);

  const readyToRun = Boolean(documentFile && selfieFile) && !processing;

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setCameraActive(false);
  }, []);

  const startCamera = useCallback(async () => {
    setCameraError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 960 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCameraActive(true);
    } catch (err) {
      console.error('Camera access failed:', err);
      setCameraError(
        err?.name === 'NotAllowedError'
          ? 'Camera permission denied. Please allow camera access and try again.'
          : 'Unable to access camera on this device.'
      );
      setCameraActive(false);
    }
  }, []);

  const capturePhoto = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !video.videoWidth) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const dataUrl = canvas.toDataURL('image/jpeg', 0.92);
    const approxSizeKb = Math.round((dataUrl.length * 3) / 4 / 1024);

    setSelfieFile({
      name: `selfie-capture-${Date.now()}.jpg`,
      type: 'image/jpeg',
      dataUrl,
      sizeKb: approxSizeKb,
    });

    stopCamera();
  }, [stopCamera]);

  // Ensure the camera stream is released whenever it's no longer needed
  useEffect(() => {
    if (selfieMode !== 'camera' && cameraActive) {
      stopCamera();
    }
  }, [selfieMode, cameraActive, stopCamera]);

  useEffect(() => {
    // Release camera on unmount
    return () => stopCamera();
  }, [stopCamera]);

  useEffect(() => {
    let cancelled = false;
    
    const checkBackend = async () => {
      const online = await checkHealth();
      if (!cancelled) {
        setBackendOnline(online);
        if (online) {
          const mod = await getModulesStatus();
          if (!cancelled) setModulesOk(mod?.all_ok);
        }
      }
    };

    const loadAuditLog = async () => {
      const entries = await getAuditLog(10);
      if (!cancelled && entries) {
        const mapped = entries.map((e) => ({
          logId: `LOG-${(e.entry_hash || '000000').slice(0, 6).toUpperCase()}`,
          timestamp: formatTimestamp(e.timestamp),
          docHash: e.document_hash,
          prevHash: e.prev_hash,
          currHash: e.entry_hash,
          verdict: e.verdict,
        }));
        setAuditLog(mapped);
      }
    };

    checkBackend();
    loadAuditLog();
    const interval = setInterval(checkBackend, 15000);
    
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [checkHealth, getModulesStatus, getAuditLog]);

  const runAnalysis = async () => {
    if (!readyToRun) return;
    if (backendOnline === false) {
      toast.error('Backend is offline. Run start.bat from the project folder first.');
      return;
    }

    setResults(null);
    setProcessing(true);
    setCurrentStep(0);

    let step = 0;
    const stepTimer = setInterval(() => {
      step += 1;
      setCurrentStep(Math.min(step, PROCESSING_STEPS.length));
    }, 800);

    try {
      const docBlob = dataUrlToBlob(documentFile.dataUrl);
      const selfieBlob = dataUrlToBlob(selfieFile.dataUrl);

      const r = await verifyDocument(docBlob, selfieBlob, docType);
      
      clearInterval(stepTimer);
      setCurrentStep(PROCESSING_STEPS.length);
      setResults(r);
      setAuditLog((log) => [r.auditEntry, ...log]);
      
      toast.success(`Analysis complete: ${r.verdict}`);
    } catch (err) {
      clearInterval(stepTimer);
      console.error('Verification failed:', err);
      toast.error(`Verification failed: ${err.message}`);
    } finally {
      setProcessing(false);
    }
  };

  const handleDocumentUpload = (file) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      setDocumentFile({
        name: file.name,
        type: file.type,
        dataUrl: e.target.result,
        sizeKb: Math.round(file.size / 1024),
      });
    };
    reader.readAsDataURL(file);
  };

  const handleSelfieUpload = (file) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      setSelfieFile({
        name: file.name,
        type: file.type,
        dataUrl: e.target.result,
        sizeKb: Math.round(file.size / 1024),
      });
    };
    reader.readAsDataURL(file);
  };

  const exportResults = () => {
    if (!results) return;
    
    const exportData = {
      timestamp: new Date().toISOString(),
      documentType: docType,
      verdict: results.verdict,
      riskScore: results.riskScore,
      ocr: results.ocr,
      validation: results.validation,
      tampering: results.tampering,
      face: results.face,
      liveness: results.liveness,
      identityGraph: results.identityGraph,
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `verification-results-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    
    toast.success('Results exported successfully');
  };

  return (
    <div className={`min-h-screen ${theme === 'dark' ? 'bg-dark-900' : 'bg-gray-50'} transition-colors duration-300`}>
      <Toaster position="top-right" />
      
      {/* Background Effects */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-primary-500/10 rounded-full blur-3xl animate-pulse-slow" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-amber-500/10 rounded-full blur-3xl animate-pulse-slow" style={{ animationDelay: '1s' }} />
      </div>

      {/* Header */}
      <header className={`sticky top-0 z-50 backdrop-blur-xl border-b ${theme === 'dark' ? 'bg-dark-900/80 border-gray-800' : 'bg-white/80 border-gray-200'}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <motion.div
                className="p-3 rounded-xl bg-gradient-to-br from-primary-500 to-primary-600 shadow-lg shadow-primary-500/25"
                whileHover={{ scale: 1.05, rotate: 5 }}
              >
                <Shield className="w-6 h-6 text-white" />
              </motion.div>
              <div>
                <h1 className={`text-xl font-bold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                  Border Control Screening
                </h1>
                <p className="text-sm text-gray-500">SIH 2026 · AI Document Verification</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowHelp(!showHelp)}
              >
                <HelpCircle className="w-4 h-4" />
              </Button>
              <ThemeToggle />
              
              <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${backendOnline ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-red-500/10 text-red-400 border border-red-500/30'}`}>
                <div className={`w-2 h-2 rounded-full ${backendOnline ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
                <span className="text-xs font-medium">
                  {backendOnline ? (modulesOk ? '8 Modules Online' : 'Backend Online') : 'Offline'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Help Modal */}
      <AnimatePresence>
        {showHelp && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
            onClick={() => setShowHelp(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className={`w-full max-w-lg rounded-2xl p-6 ${theme === 'dark' ? 'bg-dark-800 border-gray-700' : 'bg-white border-gray-200'} border shadow-2xl`}
              onClick={(e) => e.stopPropagation()}
            >
              <h2 className={`text-xl font-bold mb-4 ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                Quick Start Guide
              </h2>
              <div className="space-y-3 text-sm text-gray-600 dark:text-gray-400">
                <p><strong>1. Select Document Type:</strong> Choose the type of ID document you're verifying.</p>
                <p><strong>2. Upload Document:</strong> Upload a clear image of the ID document.</p>
                <p><strong>3. Upload Selfie:</strong> Upload a current selfie of the person.</p>
                <p><strong>4. Run Analysis:</strong> Click "Run Screening Analysis" to process.</p>
                <p><strong>5. Review Results:</strong> See the detailed analysis and risk assessment.</p>
              </div>
              <Button
                className="w-full mt-6"
                onClick={() => setShowHelp(false)}
              >
                Got it!
              </Button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        {/* Document Type Selection */}
        <Card className="mb-6">
          <CardHeader>
            <h3 className={`font-semibold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
              Document Type
            </h3>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
              {DOC_TYPES.map((type) => {
                const Icon = type.icon;
                return (
                  <motion.button
                    key={type.id}
                    onClick={() => setDocType(type.id)}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className={`p-4 rounded-xl border-2 transition-all ${
                      docType === type.id
                        ? 'border-primary-500 bg-primary-500/10'
                        : 'border-gray-700 hover:border-gray-600'
                    }`}
                  >
                    <Icon className={`w-6 h-6 mx-auto mb-2 ${docType === type.id ? 'text-primary-400' : 'text-gray-400'}`} />
                    <span className={`text-sm font-medium ${docType === type.id ? 'text-primary-400' : 'text-gray-400'}`}>
                      {type.label}
                    </span>
                  </motion.button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Upload Section */}
        <div className="grid md:grid-cols-2 gap-6 mb-6">
          {/* Document Upload */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <h3 className={`font-semibold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                  Document Upload
                </h3>
                {documentFile && (
                  <Badge variant="success">{documentFile.sizeKb} KB</Badge>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {!documentFile ? (
                <div className="border-2 border-dashed border-gray-700 rounded-xl p-8 text-center hover:border-primary-500/50 transition-colors cursor-pointer">
                  <input
                    type="file"
                    accept=".jpg,.jpeg,.png,.tiff,.tif"
                    className="hidden"
                    id="document-upload"
                    onChange={(e) => e.target.files[0] && handleDocumentUpload(e.target.files[0])}
                  />
                  <label htmlFor="document-upload" className="cursor-pointer">
                    <Upload className="w-12 h-12 mx-auto mb-4 text-gray-500" />
                    <p className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
                      Drop your document or click to browse
                    </p>
                    <p className="text-xs text-gray-500 mt-2">JPG · PNG · TIFF</p>
                  </label>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="relative rounded-lg overflow-hidden bg-dark-900">
                    <img
                      src={documentFile.dataUrl}
                      alt="Document"
                      className="w-full h-48 object-contain"
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400 truncate">{documentFile.name}</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setDocumentFile(null)}
                    >
                      Remove
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Selfie Upload */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <h3 className={`font-semibold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                  Selfie Upload
                </h3>
                {selfieFile && (
                  <Badge variant="success">{selfieFile.sizeKb} KB</Badge>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {!selfieFile ? (
                <div className="space-y-4">
                  {/* Mode Toggle */}
                  <div className={`grid grid-cols-2 gap-2 p-1 rounded-lg ${theme === 'dark' ? 'bg-dark-900' : 'bg-gray-100'}`}>
                    <button
                      type="button"
                      onClick={() => {
                        stopCamera();
                        setCameraError(null);
                        setSelfieMode('upload');
                      }}
                      className={`flex items-center justify-center gap-2 py-2 rounded-md text-sm font-medium transition-colors ${
                        selfieMode === 'upload'
                          ? 'bg-primary-500 text-white'
                          : `${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'} hover:text-gray-200`
                      }`}
                    >
                      <Upload className="w-4 h-4" />
                      Upload
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setCameraError(null);
                        setSelfieMode('camera');
                      }}
                      className={`flex items-center justify-center gap-2 py-2 rounded-md text-sm font-medium transition-colors ${
                        selfieMode === 'camera'
                          ? 'bg-primary-500 text-white'
                          : `${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'} hover:text-gray-200`
                      }`}
                    >
                      <Camera className="w-4 h-4" />
                      Take Photo
                    </button>
                  </div>

                  {selfieMode === 'upload' ? (
                    <div className="border-2 border-dashed border-gray-700 rounded-xl p-8 text-center hover:border-primary-500/50 transition-colors cursor-pointer">
                      <input
                        type="file"
                        accept=".jpg,.jpeg,.png"
                        className="hidden"
                        id="selfie-upload"
                        onChange={(e) => e.target.files[0] && handleSelfieUpload(e.target.files[0])}
                      />
                      <label htmlFor="selfie-upload" className="cursor-pointer">
                        <Camera className="w-12 h-12 mx-auto mb-4 text-gray-500" />
                        <p className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
                          Drop your selfie or click to browse
                        </p>
                        <p className="text-xs text-gray-500 mt-2">JPG · PNG</p>
                      </label>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div className="relative rounded-xl overflow-hidden bg-black aspect-[4/3] flex items-center justify-center">
                        <video
                          ref={videoRef}
                          autoPlay
                          playsInline
                          muted
                          className={`w-full h-full object-cover scale-x-[-1] ${cameraActive ? '' : 'hidden'}`}
                        />
                        {!cameraActive && (
                          <div className="flex flex-col items-center gap-3 p-6 text-center">
                            <Camera className="w-10 h-10 text-gray-500" />
                            <p className="text-sm text-gray-400">
                              {cameraError ? cameraError : 'Enable your camera to take a live selfie'}
                            </p>
                          </div>
                        )}
                      </div>
                      <canvas ref={canvasRef} className="hidden" />
                      <div className="flex gap-2">
                        {!cameraActive ? (
                          <Button
                            variant="secondary"
                            className="w-full flex items-center justify-center gap-2"
                            onClick={startCamera}
                          >
                            <Camera className="w-4 h-4" />
                            {cameraError ? 'Try Again' : 'Start Camera'}
                          </Button>
                        ) : (
                          <>
                            <Button
                              className="w-full flex items-center justify-center gap-2"
                              onClick={capturePhoto}
                            >
                              <Camera className="w-4 h-4" />
                              Capture
                            </Button>
                            <Button
                              variant="ghost"
                              onClick={stopCamera}
                            >
                              Cancel
                            </Button>
                          </>
                        )}
                      </div>
                      <p className="text-xs text-gray-500 text-center">
                        Look straight at the camera in good lighting for best results
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="relative rounded-lg overflow-hidden bg-dark-900">
                    <img
                      src={selfieFile.dataUrl}
                      alt="Selfie"
                      className="w-full h-48 object-contain"
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400 truncate">{selfieFile.name}</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setSelfieFile(null);
                        setCameraError(null);
                      }}
                    >
                      Remove
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Action Button */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
              <div>
                <p className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
                  {!readyToRun ? 'Upload both document and selfie to enable screening' : 'Ready to run analysis'}
                </p>
              </div>
              <Button
                size="lg"
                loading={processing}
                disabled={!readyToRun}
                onClick={runAnalysis}
                className="min-w-[200px]"
              >
                {processing ? 'Analyzing...' : 'Run Screening Analysis'}
              </Button>
            </div>

            {/* Processing Steps */}
            {processing && (
              <div className="mt-6 space-y-3">
                {PROCESSING_STEPS.map((step, index) => (
                  <motion.div
                    key={step}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.1 }}
                    className="flex items-center gap-3"
                  >
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center ${
                      index < currentStep
                        ? 'bg-emerald-500 text-white'
                        : index === currentStep
                        ? 'bg-primary-500 text-white animate-pulse'
                        : 'bg-gray-700 text-gray-400'
                    }`}>
                      {index < currentStep ? '✓' : index + 1}
                    </div>
                    <span className={`text-sm ${index <= currentStep ? 'text-gray-200' : 'text-gray-500'}`}>
                      {step}
                    </span>
                  </motion.div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Results */}
        <AnimatePresence>
          {results && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-6"
            >
              {/* Verdict Banner */}
              <VerdictBanner
                verdict={results.verdict}
                score={results.riskScore}
                hardGated={results.hardGated}
                hardGateReason={results.hardGateReason}
                reasons={results.reasons}
              />

              {/* Detailed Results */}
              <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-6">
                {/* OCR Results */}
                <Card delay={0.1}>
                  <CardHeader>
                    <h3 className={`font-semibold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                      OCR Results
                    </h3>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {Object.entries(results.ocr).map(([key, value]) => (
                        <div key={key} className="flex justify-between text-sm">
                          <span className="text-gray-400">{key}</span>
                          <span className={cn('truncate max-w-[150px]', theme === 'dark' ? 'text-gray-200' : 'text-gray-700')}>{value}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                {/* Validation Results */}
                <Card delay={0.2}>
                  <CardHeader>
                    <h3 className={`font-semibold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                      Validation Checks
                    </h3>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {Object.entries(results.validation).map(([key, value]) => (
                        <div key={key} className="flex items-center justify-between">
                          <span className="text-sm text-gray-400">{key}</span>
                          <Badge variant={value ? 'success' : 'danger'}>
                            {value ? 'PASS' : 'FAIL'}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                {/* Tampering Results */}
                <Card delay={0.3}>
                  <CardHeader>
                    <h3 className={`font-semibold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                      Tampering Analysis
                    </h3>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <ProgressBar label="ELA Anomaly" value={results.tampering.ela} invert />
                    <ProgressBar label="FFT Spike" value={results.tampering.fft} invert />
                    <ProgressBar label="Texture Score" value={results.tampering.cnn} invert />
                  </CardContent>
                </Card>

                {/* Face Results */}
                <Card delay={0.4}>
                  <CardHeader>
                    <h3 className={`font-semibold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                      Face Verification
                    </h3>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <ProgressBar label="Similarity" value={results.face.similarity} />
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Distance</span>
                      <span className={theme === 'dark' ? 'text-gray-200' : 'text-gray-700'}>{results.face.distance.toFixed(3)}</span>
                    </div>
                    {results.face.isReal != null && (
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-400">Anti-Spoof</span>
                        <Badge variant={results.face.isReal ? 'success' : 'danger'}>
                          {results.face.isReal ? 'REAL' : 'SPOOF'}
                        </Badge>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Liveness Results */}
                <Card delay={0.5}>
                  <CardHeader>
                    <h3 className={`font-semibold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                      Liveness Detection
                    </h3>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-400">Live Human</span>
                      <Badge variant={results.liveness.isLive ? 'success' : 'danger'}>
                        {results.liveness.isLive ? 'LIVE' : 'NOT LIVE'}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-400">Pulse Signal</span>
                      <Badge variant={results.liveness.pulseDetected ? 'success' : 'warning'}>
                        {results.liveness.pulseDetected ? 'DETECTED' : 'ABSENT'}
                      </Badge>
                    </div>
                    <ProgressBar label="Liveness Score" value={results.liveness.blinkScore} />
                  </CardContent>
                </Card>

                {/* Identity Graph */}
                {results.identityGraph && (
                  <Card delay={0.6}>
                    <CardHeader>
                      <h3 className={`font-semibold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                        Identity Graph
                      </h3>
                    </CardHeader>
                    <CardContent>
                      <div className="flex items-center justify-between mb-4">
                        <span className="text-sm text-gray-400">Cross-Document Reuse</span>
                        <Badge variant={results.identityGraph.flagged ? 'danger' : 'success'}>
                          {results.identityGraph.flagged ? 'FLAGGED' : 'CLEAR'}
                        </Badge>
                      </div>
                      {results.identityGraph.flagged && results.identityGraph.matchedId && (
                        <p className="text-sm text-red-400">
                          Prior ID: {results.identityGraph.matchedId}
                        </p>
                      )}
                    </CardContent>
                  </Card>
                )}
              </div>

              {/* Export Button */}
              <div className="flex justify-center">
                <Button
                  variant="secondary"
                  onClick={exportResults}
                  className="flex items-center gap-2"
                >
                  <Download className="w-4 h-4" />
                  Export Results
                </Button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Audit Log */}
        {auditLog.length > 0 && (
          <Card className="mt-6">
            <CardHeader>
              <div className="flex items-center justify-between">
                <h3 className={`font-semibold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                  Audit Trail
                </h3>
                <BarChart3 className="w-5 h-5 text-gray-400" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {auditLog.map((entry, index) => (
                  <motion.div
                    key={entry.logId}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className={`p-4 rounded-lg border ${theme === 'dark' ? 'bg-dark-900 border-gray-800' : 'bg-gray-50 border-gray-200'}`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-mono text-gray-400">{entry.logId}</span>
                      <Badge variant={entry.verdict === 'GENUINE' ? 'success' : entry.verdict === 'SUSPICIOUS' ? 'warning' : 'danger'}>
                        {entry.verdict}
                      </Badge>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <span className="text-gray-500">Doc Hash:</span>
                        <span className="ml-2 text-gray-400 font-mono">{truncateHash(entry.docHash)}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Time:</span>
                        <span className="ml-2 text-gray-400">{entry.timestamp}</span>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </main>

      {/* Footer */}
      <footer className={`border-t ${theme === 'dark' ? 'border-gray-800' : 'border-gray-200'} mt-12 py-6`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 text-center text-sm text-gray-500">
          <p>SIH 2026 · AI-Based Fake Identity & Document Screening System</p>
          <p className="mt-1">Hash-chained audit · 8-module fusion pipeline</p>
        </div>
      </footer>
    </div>
  );
}