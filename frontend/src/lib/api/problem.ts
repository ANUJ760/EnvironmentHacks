export interface ProblemDetails {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  instance?: string;
  code?: string;
  request_id?: string;
  missing_inputs?: string[];
  [key: string]: unknown;
}

export class ApiError extends Error {
  public status: number;
  public code?: string;
  public requestId?: string;
  public missingInputs?: string[];
  public details?: ProblemDetails;

  constructor(status: number, message: string, details?: ProblemDetails) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = details?.code;
    this.requestId = details?.request_id;
    this.missingInputs = details?.missing_inputs;
    this.details = details;
  }
}

export function parseProblemDetails(status: number, data: unknown): ApiError {
  if (typeof data === 'object' && data !== null) {
    const p = data as ProblemDetails;
    const code = p.code || (p as { error_code?: string }).error_code;
    const detail = p.detail || (p as { message?: string }).message || p.title || 'An unexpected API error occurred';
    return new ApiError(status, detail, {
      ...p,
      code,
      detail,
    });
  }
  return new ApiError(status, `HTTP error ${status}`);
}

export function getHumanErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    switch (err.code) {
      case 'CITY_NOT_FOUND':
        return 'City study area not found. Please select a registered city from the directory.';
      case 'DATASET_NOT_READY':
        return 'Required city dataset is still ingesting or unavailable. Try again shortly.';
      case 'STALE_WEATHER':
        return 'Weather data is stale. Simulations requiring current conditions are temporarily blocked.';
      case 'OPENAQ_CREDENTIAL_REQUIRED':
        return 'Air quality provider credentials not configured on the backend.';
      case 'MODEL_NOT_AVAILABLE':
        return 'Requested simulation model is currently unavailable for this study area.';
      case 'INSUFFICIENT_INPUT_DATA':
        return `Missing prerequisite inputs: ${err.missingInputs?.join(', ') || 'check model requirements'}.`;
      case 'SCENARIO_VERSION_CONFLICT':
        return 'Scenario was modified by another session. Please review changes and reload.';
      case 'IDEMPOTENCY_CONFLICT':
        return 'Duplicate request with conflicting parameters was rejected.';
      case 'INVALID_GEOMETRY':
        return 'Intervention geometry is invalid (self-intersecting or invalid coordinates).';
      case 'OUTSIDE_STUDY_BOUNDARY':
        return 'The selected polygon extends outside the official city study area boundary.';
      case 'STORAGE_UNAVAILABLE':
        return 'Storage service is temporarily unavailable. Retrying with backoff...';
    }

    if (err.status === 401) return 'Authentication required. Please sign in or check your access token.';
    if (err.status === 403) return 'You do not have permission to view or modify this resource.';
    if (err.status === 412) return 'Concurrency conflict (ETag precondition failed). Please refresh.';
    if (err.status === 429) return 'Rate limit exceeded. Please wait a moment before trying again.';
    if (err.status >= 500) return 'The server encountered an error processing your request. Please try again later.';

    return err.message;
  }

  if (err instanceof Error) return err.message;
  return 'An unknown error occurred.';
}
