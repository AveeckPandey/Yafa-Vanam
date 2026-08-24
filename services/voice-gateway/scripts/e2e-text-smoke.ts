/**
 * Milestone-1 E2E smoke: drives the gateway exactly like the YAFA UI will.
 *
 * Nova 2 Sonic is voice-first: once promptStart/systemPrompt/audioStart
 * declare the session, it expects USER audio bytes on the interactive AUDIO
 * content block. Typed messages ride ALONGSIDE the open mic (as they will in
 * the YAFA chat UI). So this smoke:
 *   initialize -> promptStart -> systemPrompt -> audioStart
 *     -> pumps ~silence on audioInput (like an open, quiet microphone)
 *     -> sends textInput("Hi Yafa.")
 *     -> collects ASSISTANT textOutput.
 */
import { io } from "socket.io-client";

const GATEWAY = process.env.GATEWAY_URL || "http://localhost:3008";
const SAMPLE_RATE = 16000;
const CHUNK_MS = 100;
const CHUNK_BYTES = (SAMPLE_RATE / 1000) * CHUNK_MS * 2; // mono, s16le

const socket = io(GATEWAY, { transports: ["websocket"] });
let assistantText = "";
let done = false;
let silencePump: ReturnType<typeof setInterval> | null = null;

const timeout = setTimeout(() => {
    console.error("TIMEOUT - partial transcript below");
    finish(2);
}, 90_000);

function finish(code: number) {
    if (done) return;
    done = true;
    clearTimeout(timeout);
    if (silencePump) clearInterval(silencePump);
    console.log("\n=== RESULT ===");
    console.log(`yafa said  : ${assistantText || "(nothing)"}`);
    console.log(code === 0 ? "PASS" : "FAIL");
    socket.emit("stopAudio");
    socket.disconnect();
    process.exit(code);
}

function startSilencePump() {
    const silence = Buffer.alloc(CHUNK_BYTES); // zeros = quiet room
    silencePump = setInterval(() => {
        socket.emit("audioInput", silence.toString("base64"));
    }, CHUNK_MS);
}

socket.on("connect", () => {
    console.log(`[smoke] connected as ${socket.id}`);

    socket.emit("initializeConnection", { region: process.env.AWS_REGION || "us-east-1" }, async (res: any) => {
        if (!res?.success) {
            console.error("[smoke] initialize failed:", res);
            finish(1);
            return;
        }
        console.log("[smoke] session initialized");

        // Proven sample sequence (voice-first):
        socket.emit("promptStart", {});
        await new Promise(r => setTimeout(r, 300));
        socket.emit("systemPrompt", {});
        await new Promise(r => setTimeout(r, 300));
        socket.emit("audioStart");
    });
});

socket.on("audioReady", async () => {
    console.log("[smoke] stream ACTIVE - opening mic (silence) then sending 'Hi Yafa.'");
    startSilencePump();
    await new Promise(r => setTimeout(r, 1200));
    socket.emit("textInput", { content: "Hi Yafa." });
});

socket.on("textOutput", (data: any) => {
    const content = data?.content ?? "";
    if (data?.role === "ASSISTANT") {
        assistantText += content;
        process.stdout.write(content);
        if (/[.!?]$/.test(assistantText.trim()) && assistantText.trim().length > 10) {
            console.log("");
            finish(0);
        }
    }
});

socket.on("error", (err: any) => {
    console.error("[gateway error]", JSON.stringify(err).substring(0, 300));
    finish(3);
});

socket.on("streamComplete", () => {
    console.log("\n[smoke] stream completed");
    finish(assistantText ? 0 : 3);
});
