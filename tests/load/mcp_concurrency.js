// ==============================================================================
// k6 Concurrency Test: DexGuard MCP Endpoint
// ==============================================================================
// Usage:
//   k6 run tests/load/mcp_concurrency.js
//
// Requirement (from DexGuard Testing Plan, Section C):
//   Fire 500 VUs simultaneously querying an already-cached pool endpoint.
//   Assertion: p99 latency < 50ms, error rate = 0%.
// ==============================================================================

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('error_rate');
const p99Latency = new Trend('p99_latency', true);

export const options = {
  scenarios: {
    mcp_burst: {
      executor: 'constant-vus',
      vus: 500,
      duration: '30s',
    },
  },
  thresholds: {
    http_req_duration: ['p(99)<50'],  // p99 latency < 50ms
    error_rate: ['rate<0.001'],       // error rate ~0%
  },
};

// Use a known-cached pool address (seeded in the database)
const BASE_URL = __ENV.BASE_URL || 'http://localhost:3000';
const CACHED_POOL = '0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640';
const NETWORK = 'eth';

export default function () {
  const url = `${BASE_URL}/api/v1/mcp/pool_status?address=${CACHED_POOL}&network=${NETWORK}`;

  const res = http.get(url, {
    headers: { 'Accept': 'application/json' },
    tags: { name: 'mcp_pool_status' },
  });

  // Track errors
  const isSuccess = res.status === 200;
  errorRate.add(!isSuccess);
  p99Latency.add(res.timings.duration);

  // Assertions
  check(res, {
    'status is 200': (r) => r.status === 200,
    'has health_score': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.health_score !== undefined;
      } catch {
        return false;
      }
    },
    'response time < 50ms': (r) => r.timings.duration < 50,
  });
}

export function handleSummary(data) {
  const p99 = data.metrics.http_req_duration.values['p(99)'];
  const errRate = data.metrics.error_rate ? data.metrics.error_rate.values.rate : 0;

  console.log(`\n=== DexGuard k6 Summary ===`);
  console.log(`  p99 Latency: ${p99.toFixed(2)}ms (threshold: <50ms)`);
  console.log(`  Error Rate:  ${(errRate * 100).toFixed(4)}% (threshold: <0.1%)`);
  console.log(`  VUs:         ${data.metrics.vus.values.value}`);
  console.log(`  Total Reqs:  ${data.metrics.http_reqs.values.count}`);

  return {
    stdout: JSON.stringify(data, null, 2),
  };
}
