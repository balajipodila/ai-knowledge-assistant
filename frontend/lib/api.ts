import { clearSession, readSession } from "./session";

export const SESSION_EXPIRED_EVENT = "aka:session-expired";

export type ApiErrorFields = Record<string, string>;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: ApiErrorFields;

  constructor(
    message: string,
    status: number,
    code: string,
    fields: ApiErrorFields = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  timeoutMs?: number;
  auth?: boolean;
};

type ErrorBody = {
  error?: {
    code?: unknown;
    message?: unknown;
  };
  detail?: unknown;
};

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")
  .replace(/\/+$/, "");

function validationFields(detail: unknown): ApiErrorFields {
  if (!Array.isArray(detail)) {
    return {};
  }
  const fields: ApiErrorFields = {};
  for (const item of detail) {
    if (
      typeof item === "object" &&
      item !== null &&
      "loc" in item &&
      Array.isArray(item.loc) &&
      "msg" in item &&
      typeof item.msg === "string"
    ) {
      const field = item.loc.at(-1);
      if (typeof field === "string") {
        fields[field] = item.msg;
      }
    }
  }
  return fields;
}

function friendlyError(status: number, code: string): string {
  const documentUploadErrors: Record<string, string> = {
    UNSUPPORTED_FILE_EXTENSION: "Only PDF files are accepted.",
    UNSUPPORTED_MEDIA_TYPE: "The selected file must be a PDF.",
    EMPTY_FILE: "The selected PDF is empty.",
    FILE_TOO_LARGE: "The PDF exceeds the server's configured size limit.",
    INVALID_PDF_SIGNATURE: "The file does not appear to be a valid PDF.",
    PDF_ENCRYPTED: "Password-protected PDFs are not supported.",
    PDF_EMPTY: "The PDF does not contain any pages.",
    PDF_TOO_MANY_PAGES: "The PDF exceeds the server's page limit.",
    PDF_INVALID: "The uploaded file is not a readable PDF.",
    PDF_NO_TEXT: "No selectable text was found in the PDF. Scanned PDFs are not supported yet.",
  };
  if (documentUploadErrors[code]) return documentUploadErrors[code];
  if (status === 401) return "Email or password is incorrect.";
  if (status === 409) return "An account with this email already exists.";
  if (status === 422) return "Check the highlighted fields and try again.";
  if (status === 429) return "The service is busy. Please try again in a minute.";
  if (status === 503 || status >= 500) {
    return "The service is temporarily unavailable. Please try again shortly.";
  }
  if (code === "NOT_FOUND") return "The requested item could not be found.";
  return "We could not complete that request. Please try again.";
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const {
    body,
    timeoutMs = 15000,
    auth = true,
    headers: inputHeaders,
    ...requestOptions
  } = options;
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  const headers = new Headers(inputHeaders);
  headers.set("Accept", "application/json");

  if (body !== undefined && !(body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (auth) {
    const session = readSession();
    if (session) {
      headers.set("Authorization", `Bearer ${session.accessToken}`);
    }
  }

  try {
    const response = await fetch(`${API_URL}${path}`, {
      ...requestOptions,
      method: requestOptions.method ?? (body === undefined ? "GET" : "POST"),
      headers,
      body:
        body === undefined
          ? undefined
          : body instanceof FormData
            ? body
            : JSON.stringify(body),
      signal: controller.signal,
    });

    if (response.status === 401 && auth) {
      const hadSession = readSession() !== null;
      clearSession();
      if (hadSession) {
        window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
      }
    }

    if (!response.ok) {
      let payload: ErrorBody = {};
      try {
        payload = (await response.json()) as ErrorBody;
      } catch {
        payload = {};
      }
      const error = payload.error;
      const code =
        typeof error?.code === "string" ? error.code : "REQUEST_FAILED";
      throw new ApiError(
        friendlyError(response.status, code),
        response.status,
        code,
        validationFields(payload.detail),
      );
    }

    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(
        "That request took too long. Please try again.",
        0,
        "REQUEST_TIMEOUT",
      );
    }
    throw new ApiError(
      "Could not connect to the service. Check your connection and try again.",
      0,
      "NETWORK_ERROR",
    );
  } finally {
    window.clearTimeout(timeout);
  }
}
