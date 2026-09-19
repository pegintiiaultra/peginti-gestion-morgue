import request from 'supertest';
import app from '../index.js';

describe('GET /api/health', () => {
  it('devrait retourner un statut 200 et le bon moteur', async () => {
    const response = await request(app).get('/api/health');
    expect(response.statusCode).toBe(200);
    expect(response.body).toHaveProperty('status', 'ONLINE');
    expect(response.body.engine).toContain("bo'oivinichat");
  });
});
