import { useState, useCallback } from 'react';

const API_URL = "https://border-document-detection-1.onrender.com";
export function useApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const verifyDocument = useCallback(async (documentImage, selfiePhoto, docType) => {
    setLoading(true);
    setError(null);
    
    try {
      const formData = new FormData();
      formData.append("document_image", documentImage, "document.jpg");
      formData.append("selfie_photo", selfiePhoto, "selfie.png");
      formData.append("doc_type", docType);

      const response = await fetch(`${API_URL}/verify`, { 
        method: "POST", 
        body: formData 
      });
      
      if (!response.ok) {
        const errBody = await response.json().catch(() => ({}));
        throw new Error(errBody.error || `Server returned ${response.status}`);
      }
      
      return await response.json();
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const checkHealth = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/health`);
      return response.ok;
    } catch {
      return false;
    }
  }, []);

  const getModulesStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/modules/status`);
      if (response.ok) {
        return await response.json();
      }
    } catch {
      return null;
    }
  }, []);

  const getAuditLog = useCallback(async (limit = 10) => {
    try {
      const response = await fetch(`${API_URL}/audit-log?limit=${limit}`);
      if (response.ok) {
        return await response.json();
      }
    } catch {
      return [];
    }
  }, []);

  return { 
    verifyDocument, 
    checkHealth, 
    getModulesStatus, 
    getAuditLog, 
    loading, 
    error 
  };
}