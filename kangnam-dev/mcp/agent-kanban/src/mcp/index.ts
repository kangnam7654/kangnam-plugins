import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const execFileAsync = promisify(execFile);
const here = path.dirname(fileURLToPath(import.meta.url));

const server = new McpServer(
  {
    name: "agent-kanban",
    version: "0.1.0"
  },
  {
    instructions:
      "Project-local Kanban adapter. Prefer the CLI directly when available. Through MCP, call kanban_context at session start and kanban_run for explicit agent-kanban CLI commands."
  }
);

server.registerTool(
  "kanban_context",
  {
    title: "Get Kanban Context",
    description: "Compact session-start context for the project board at <project-root>/.kanban/kanban-data.json.",
    inputSchema: z
      .object({
        cwd: z.string().min(1).describe("Current project working directory."),
        branch: z.string().min(1).optional().describe("Current branch, if known."),
        session: z.string().min(1).optional().describe("Stable agent session id, if available."),
        json: z.boolean().default(false).describe("Return raw JSON instead of compact text.")
      })
      .strict(),
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false
    }
  },
  async (input) => {
    const args = ["context", "--cwd", input.cwd];
    if (input.branch) args.push("--branch", input.branch);
    if (input.session) args.push("--session", input.session);
    if (input.json) args.push("--json");
    return runCliTool(args);
  }
);

server.registerTool(
  "kanban_run",
  {
    title: "Run Agent Kanban CLI",
    description:
      "Run one agent-kanban CLI command. Examples: ['create','Fix login','--cwd','/repo','--status','ready'], ['claim','AK-1','--cwd','/repo','--session','s1'], ['progress','AK-1','--cwd','/repo','--msg','Implemented parser','--files','src/parser.ts'].",
    inputSchema: z
      .object({
        args: z.array(z.string().min(1)).min(1).describe("Arguments after the agent-kanban binary name."),
        cwd: z.string().min(1).optional().describe("Process working directory. The command should still pass --cwd for board routing.")
      })
      .strict(),
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
      idempotentHint: false,
      openWorldHint: false
    }
  },
  async (input) => runCliTool(input.args, input.cwd)
);

const transport = new StdioServerTransport();
await server.connect(transport);
console.error("agent-kanban MCP adapter running on stdio.");

async function runCliTool(args: string[], cwd?: string | undefined) {
  try {
    const output = await runAgentKanban(args, cwd);
    return {
      content: [{ type: "text" as const, text: output || "(no output)" }],
      structuredContent: { output }
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      isError: true,
      content: [{ type: "text" as const, text: message }]
    };
  }
}

async function runAgentKanban(args: string[], cwd?: string | undefined): Promise<string> {
  const command = findCliCommand();
  const { stdout, stderr } = await execFileAsync(command.bin, [...command.prefixArgs, ...args], {
    cwd: cwd || process.cwd(),
    env: process.env,
    maxBuffer: 1024 * 1024
  });

  return [stdout.trim(), stderr.trim()].filter(Boolean).join("\n");
}

function findCliCommand(): { bin: string; prefixArgs: string[] } {
  const builtCli = path.resolve(here, "../cli/index.js");
  if (existsSync(builtCli)) {
    return { bin: process.execPath, prefixArgs: [builtCli] };
  }

  const sourceCli = path.resolve(here, "../cli/index.ts");
  if (existsSync(sourceCli)) {
    return { bin: "tsx", prefixArgs: [sourceCli] };
  }

  throw new Error("Cannot find agent-kanban CLI. Run npm run build first.");
}
