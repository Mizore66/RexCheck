/**
 * RexCheck MCP Server
 *
 * A Model Context Protocol (MCP) server that exposes DeFi pool health analysis
 * as callable tools for AI agents (Claude Desktop, OpenClaw, etc.)
 *
 * Transport: stdio (standard for Claude Desktop integration)
 *
 * Usage:
 *   node index.js
 *
 * Environment variables:
 *   RAILS_API_URL  — Base URL of the Rails app (default: http://localhost:3000)
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const RAILS_API_URL = process.env.RAILS_API_URL ?? "http://localhost:3000";

// ---------------------------------------------------------------------------
// Static fallback dataset (used when Rails is unreachable)
// Mirrors the seed data so the agent always gets a useful response.
// ---------------------------------------------------------------------------
const STATIC_TOKENS = {
  WETH: {
    symbol: "WETH",
    pool_count: 2,
    avg_health_score: 52,
    min_health_score: 20,
    max_health_score: 85,
    overall_status: "WARNING",
    recommendation: "MONITOR_CLOSELY",
    flags: ["critical_low_liquidity", "unseasoned_pool"],
    networks: ["base", "optimism"],
    pools: [
      {
        pool_address: "0xcDAC0d6c6C59727a65F871236188350531885C43",
        network: "base",
        pair: "WETH/USDC",
        health_score: 20,
        status: "DANGER",
        recommendation: "DO_NOT_TRADE",
        flags: ["critical_low_liquidity", "unseasoned_pool"],
        volume_usd: 3200,
        reserve_in_usd: 5000,
      },
      {
        pool_address: "0x68F5C0A2DE713a54991E01858Fd27a3832401849",
        network: "optimism",
        pair: "WETH/USDC",
        health_score: 85,
        status: "SAFE",
        recommendation: "TRADE_WITH_CAUTION",
        flags: [],
        volume_usd: 750000,
        reserve_in_usd: 18000000,
      },
    ],
  },
  ETH: {
    symbol: "ETH",
    pool_count: 1,
    avg_health_score: 100,
    min_health_score: 100,
    max_health_score: 100,
    overall_status: "SAFE",
    recommendation: "TRADE_WITH_CAUTION",
    flags: [],
    networks: ["eth"],
    pools: [
      {
        pool_address: "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
        network: "eth",
        pair: "USDC/WETH",
        health_score: 100,
        status: "SAFE",
        recommendation: "TRADE_WITH_CAUTION",
        flags: [],
        volume_usd: 2500000,
        reserve_in_usd: 150000000,
      },
    ],
  },
  SOL: {
    symbol: "SOL",
    pool_count: 2,
    avg_health_score: 100,
    min_health_score: 100,
    max_health_score: 100,
    overall_status: "SAFE",
    recommendation: "TRADE_WITH_CAUTION",
    flags: [],
    networks: ["solana"],
    pools: [
      {
        pool_address: "7qbRF6YsyGuLUVs6Y1q64bdVrfe4ZcUUz1JRdoVNUJnm",
        network: "solana",
        pair: "SOL/USDC",
        health_score: 100,
        status: "SAFE",
        recommendation: "TRADE_WITH_CAUTION",
        flags: [],
        volume_usd: 12000000,
        reserve_in_usd: 80000000,
      },
      {
        pool_address: "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP",
        network: "solana",
        pair: "SOL/WBTC",
        health_score: 100,
        status: "SAFE",
        recommendation: "TRADE_WITH_CAUTION",
        flags: [],
        volume_usd: 980000,
        reserve_in_usd: 6200000,
      },
    ],
  },
  WBTC: {
    symbol: "WBTC",
    pool_count: 2,
    avg_health_score: 55,
    min_health_score: 70,
    max_health_score: 100,
    overall_status: "WARNING",
    recommendation: "MONITOR_CLOSELY",
    flags: ["wash_trading_suspected"],
    networks: ["arbitrum", "eth"],
    pools: [
      {
        pool_address: "0xc31e54c7a869b9fcbecc14363cf510d1c41fa443",
        network: "arbitrum",
        pair: "WBTC/USDC",
        health_score: 70,
        status: "WARNING",
        recommendation: "MONITOR_CLOSELY",
        flags: ["wash_trading_suspected"],
        volume_usd: 15000000,
        reserve_in_usd: 200000,
      },
      {
        pool_address: "0xcbcdf9626bc03e24f779434178a73a0b4bad62ed",
        network: "eth",
        pair: "WBTC/WETH",
        health_score: 100,
        status: "SAFE",
        recommendation: "TRADE_WITH_CAUTION",
        flags: [],
        volume_usd: 8000000,
        reserve_in_usd: 320000000,
      },
    ],
  },
  USDC: {
    symbol: "USDC",
    pool_count: 3,
    avg_health_score: 90,
    min_health_score: 70,
    max_health_score: 100,
    overall_status: "SAFE",
    recommendation: "TRADE_WITH_CAUTION",
    flags: [],
    networks: ["eth", "solana", "arbitrum"],
    pools: [
      {
        pool_address: "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
        network: "eth",
        pair: "USDC/WETH",
        health_score: 100,
        status: "SAFE",
        recommendation: "TRADE_WITH_CAUTION",
        flags: [],
        volume_usd: 2500000,
        reserve_in_usd: 150000000,
      },
      {
        pool_address: "7qbRF6YsyGuLUVs6Y1q64bdVrfe4ZcUUz1JRdoVNUJnm",
        network: "solana",
        pair: "SOL/USDC",
        health_score: 100,
        status: "SAFE",
        recommendation: "TRADE_WITH_CAUTION",
        flags: [],
        volume_usd: 12000000,
        reserve_in_usd: 80000000,
      },
      {
        pool_address: "0xc31e54c7a869b9fcbecc14363cf510d1c41fa443",
        network: "arbitrum",
        pair: "WBTC/USDC",
        health_score: 70,
        status: "WARNING",
        recommendation: "MONITOR_CLOSELY",
        flags: ["wash_trading_suspected"],
        volume_usd: 15000000,
        reserve_in_usd: 200000,
      },
    ],
  },
};

const STATIC_POOLS = {
  "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640": {
    pool_address: "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
    status: "SAFE",
    health_score: 100,
    recommendation: "TRADE_WITH_CAUTION",
    flags: [],
  },
  "0xcDAC0d6c6C59727a65F871236188350531885C43": {
    pool_address: "0xcDAC0d6c6C59727a65F871236188350531885C43",
    status: "DANGER",
    health_score: 20,
    recommendation: "DO_NOT_TRADE",
    flags: ["critical_low_liquidity", "unseasoned_pool"],
  },
  "0xc31e54c7a869b9fcbecc14363cf510d1c41fa443": {
    pool_address: "0xc31e54c7a869b9fcbecc14363cf510d1c41fa443",
    status: "WARNING",
    health_score: 70,
    recommendation: "MONITOR_CLOSELY",
    flags: ["wash_trading_suspected"],
  },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function fetchRails(path) {
  const url = `${RAILS_API_URL}${path}`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const res = await fetch(url, {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      return { ok: false, status: res.status, data: body };
    }
    return { ok: true, data: await res.json() };
  } catch (err) {
    clearTimeout(timeout);
    return { ok: false, error: err.message };
  }
}

function formatAnalysis(data) {
  const poolLines = data.pools
    .map(
      (p) =>
        `  • ${p.pair ?? p.pool_address} [${p.network.toUpperCase()}] — Score: ${p.health_score} (${p.status})${p.flags.length ? " — Flags: " + p.flags.join(", ") : ""}`
    )
    .join("\n");

  return (
    `Token: ${data.symbol}\n` +
    `Overall Status: ${data.overall_status}  |  Avg Health Score: ${data.avg_health_score}/100\n` +
    `Recommendation: ${data.recommendation.replace(/_/g, " ")}\n` +
    `Networks: ${data.networks.join(", ")}\n` +
    `Pools (${data.pool_count}):\n${poolLines}` +
    (data.flags.length ? `\nRisk Flags: ${data.flags.join(", ")}` : "")
  );
}

function formatPoolStatus(data) {
  return (
    `Pool: ${data.pool_address}\n` +
    `Status: ${data.status}  |  Health Score: ${data.health_score}/100\n` +
    `Recommendation: ${data.recommendation.replace(/_/g, " ")}` +
    (data.flags.length ? `\nFlags: ${data.flags.join(", ")}` : "")
  );
}

// ---------------------------------------------------------------------------
// MCP Server
// ---------------------------------------------------------------------------

const server = new McpServer({
  name: "rexcheck",
  version: "1.0.0",
});

// Tool 1: analyze_token
server.tool(
  "analyze_token",
  "Analyze the DeFi risk profile of a cryptocurrency token. Returns aggregated health scores, risk flags, and pool breakdown across all tracked networks.",
  {
    symbol: z
      .string()
      .min(1)
      .max(20)
      .describe("Token symbol, e.g. ETH, SOL, USDC, WBTC, WETH, UNI, LINK"),
    network: z
      .string()
      .optional()
      .describe(
        "Optional: filter by network (eth, solana, base, arbitrum, polygon_pos, bsc, avalanche, optimism)"
      ),
  },
  async ({ symbol, network }) => {
    const query = new URLSearchParams({ symbol });
    if (network) query.set("network", network);

    const result = await fetchRails(
      `/api/v1/mcp/token_analysis?${query.toString()}`
    );

    if (result.ok) {
      return {
        content: [
          {
            type: "text",
            text: formatAnalysis(result.data),
          },
          {
            type: "text",
            text: JSON.stringify(result.data, null, 2),
          },
        ],
      };
    }

    // Fallback to static data
    const sym = symbol.toUpperCase();
    const staticData = STATIC_TOKENS[sym];

    if (staticData) {
      const filtered = network
        ? {
            ...staticData,
            pools: staticData.pools.filter((p) => p.network === network),
          }
        : staticData;

      return {
        content: [
          {
            type: "text",
            text:
              "[Using cached sample data — Rails not reachable]\n\n" +
              formatAnalysis(filtered),
          },
          { type: "text", text: JSON.stringify(filtered, null, 2) },
        ],
      };
    }

    return {
      content: [
        {
          type: "text",
          text: `No data found for token ${symbol.toUpperCase()}. Tracked tokens: ${Object.keys(STATIC_TOKENS).join(", ")}`,
        },
      ],
      isError: true,
    };
  }
);

// Tool 2: get_pool_status
server.tool(
  "get_pool_status",
  "Get the health status and risk score for a specific liquidity pool by its contract address and network.",
  {
    address: z
      .string()
      .min(10)
      .describe("Pool contract address (e.g. 0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640)"),
    network: z
      .string()
      .min(2)
      .describe(
        "Network identifier: eth, solana, base, arbitrum, polygon_pos, bsc, avalanche, optimism"
      ),
  },
  async ({ address, network }) => {
    const query = new URLSearchParams({ address, network });
    const result = await fetchRails(
      `/api/v1/mcp/pool_status?${query.toString()}`
    );

    if (result.ok) {
      return {
        content: [
          { type: "text", text: formatPoolStatus(result.data) },
          { type: "text", text: JSON.stringify(result.data, null, 2) },
        ],
      };
    }

    // Fallback
    const staticPool = STATIC_POOLS[address.toLowerCase()] ?? STATIC_POOLS[address];
    if (staticPool) {
      return {
        content: [
          {
            type: "text",
            text:
              "[Using cached sample data — Rails not reachable]\n\n" +
              formatPoolStatus(staticPool),
          },
          { type: "text", text: JSON.stringify(staticPool, null, 2) },
        ],
      };
    }

    return {
      content: [
        {
          type: "text",
          text: result.data?.error ?? `Pool not found: ${address} on ${network}`,
        },
      ],
      isError: true,
    };
  }
);

// Tool 3: list_tokens
server.tool(
  "list_tokens",
  "List all cryptocurrency tokens currently tracked by RexCheck with their monitoring status.",
  {},
  async () => {
    const staticList = [
      { symbol: "WETH", networks: ["base", "optimism"], note: "Wrapped Ether" },
      { symbol: "ETH",  networks: ["eth"],              note: "Ethereum (as USDC/WETH pair)" },
      { symbol: "USDC", networks: ["eth", "solana", "arbitrum", "base", "polygon_pos", "avalanche", "optimism"], note: "USD Coin" },
      { symbol: "SOL",  networks: ["solana"],            note: "Solana" },
      { symbol: "WBTC", networks: ["eth", "arbitrum"],   note: "Wrapped Bitcoin" },
      { symbol: "UNI",  networks: ["eth"],               note: "Uniswap governance token" },
      { symbol: "LINK", networks: ["eth"],               note: "Chainlink" },
      { symbol: "MATIC",networks: ["polygon_pos"],       note: "Polygon" },
      { symbol: "BNB",  networks: ["bsc"],               note: "BNB Chain" },
      { symbol: "AVAX", networks: ["avalanche"],         note: "Avalanche" },
      { symbol: "BUSD", networks: ["bsc"],               note: "Binance USD" },
    ];

    // Prefer live list from Rails.
    const liveResult = await fetchRails("/api/v1/mcp/list_tokens");
    if (liveResult.ok && Array.isArray(liveResult.data?.tokens)) {
      const lines = liveResult.data.tokens
        .map((t) => `  • ${String(t.symbol).padEnd(6)} — Pools: ${t.pool_count} [${(t.networks ?? []).join(", ")}]`)
        .join("\n");

      return {
        content: [
          {
            type: "text",
            text:
              `Tracked tokens (${liveResult.data.token_count}) — Rails connected:\n` +
              lines +
              `\n\nTo analyze any token, use the analyze_token tool with its symbol.`,
          },
          {
            type: "text",
            text: JSON.stringify(liveResult.data, null, 2),
          },
        ],
      };
    }

    const lines = staticList
      .map((t) => `  • ${t.symbol.padEnd(6)} — ${t.note} [${t.networks.join(", ")}]`)
      .join("\n");

    return {
      content: [
        {
          type: "text",
          text:
            `Tracked tokens (${staticList.length}) — cached list:\n` +
            lines +
            `\n\nTo analyze any token, use the analyze_token tool with its symbol.`,
        },
        {
          type: "text",
          text: JSON.stringify({ token_count: staticList.length, tokens: staticList }, null, 2),
        },
      ],
    };
  }
);

// Tool 4: ping
server.tool(
  "ping",
  "Quick health check for MCP connectivity and Rails backend reachability.",
  {},
  async () => {
    const check = await fetchRails("/up");
    return {
      content: [
        {
          type: "text",
          text: check.ok
            ? "rexcheck MCP is running. Rails backend is reachable."
            : "rexcheck MCP is running. Rails backend is currently unreachable (fallback data may be used).",
        },
      ],
    };
  }
);

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

const transport = new StdioServerTransport();
await server.connect(transport);
