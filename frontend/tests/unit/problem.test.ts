import { describe, it, expect } from 'vitest';
import { parseProblemDetails, getHumanErrorMessage, ApiError } from '@/lib/api/problem';

describe('Problem Details Error Handling', () => {
  it('parses RFC 7807 problem json payloads', () => {
    const payload = {
      type: 'about:blank',
      title: 'City Not Found',
      status: 404,
      detail: 'Study area not registered in database',
      code: 'CITY_NOT_FOUND',
      request_id: 'req-12345',
    };

    const err = parseProblemDetails(404, payload);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(404);
    expect(err.code).toBe('CITY_NOT_FOUND');
    expect(err.requestId).toBe('req-12345');
    expect(err.message).toBe('Study area not registered in database');
  });

  it('maps backend error codes to human-readable actionable messages', () => {
    const err = new ApiError(404, 'NotFound', { code: 'CITY_NOT_FOUND' });
    expect(getHumanErrorMessage(err)).toContain('City study area not found');

    const conflictErr = new ApiError(412, 'Precondition Failed', { code: 'SCENARIO_VERSION_CONFLICT' });
    expect(getHumanErrorMessage(conflictErr)).toContain('Scenario was modified by another session');

    const geomErr = new ApiError(422, 'Unprocessable Entity', { code: 'INVALID_GEOMETRY' });
    expect(getHumanErrorMessage(geomErr)).toContain('Intervention geometry is invalid');
  });
});
