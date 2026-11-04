export type User = {
  id: string;
  email: string;
  created_at: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
};

export type DocumentItem = {
  id: string;
  filename: string;
  status: "processing" | "ready" | "failed" | "embedding_failed" | string;
  page_count: number;
  created_at: string;
  failure_reason: string | null;
};

export type DocumentUploadResponse = DocumentItem & {
  chunk_count: number;
  duplicate: boolean;
};

export type Citation = {
  number: number;
  document_id: string;
  filename: string;
  page_number: number;
  snippet: string;
};

export type ChatResponse = {
  answer: string;
  citations: Citation[];
};
