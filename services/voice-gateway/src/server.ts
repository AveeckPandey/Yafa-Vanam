/**
 * YAFA VANAM voice gateway server.
 *
 * Socket.IO contract is IDENTICAL to the proven AWS nova-sonic sample so the
 * YAFA frontend can adopt it directly (and so the sample's browser client can
 * be pointed at this server for verification before the YAFA UI is wired).
 *
 * Differences from the sample, on purpose:
 * - no static frontend serving (YAFA's Next.js UI owns the browser side)
 * - CORS locked to ALLOWED_ORIGINS
 * - binds localhost by default; never expose without auth in production
 * - port 3008 to avoid colliding with Next.js (:3000)
 */
import express from 'express';
import http from 'http';
import { Server } from 'socket.io';
import dotenv from 'dotenv';
import { NovaSonicBidirectionalStreamClient, StreamSession } from './client';
import { Buffer } from 'node:buffer';
import { YafaConfig } from './consts';
import { YAFA_SYSTEM_PROMPT } from './yafa-prompt';
import {
    FixedWindowRateLimiter,
    clientAddress,
    validateCustomerText,
    verifyGatewayToken,
} from './security';

dotenv.config();

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
    cors: {
        origin: YafaConfig.allowedOrigins,
        methods: ['GET', 'POST'],
    },
});

// One Bedrock client per region (HTTP/2 multiplexing is per-client).
const regionClients = new Map<string, NovaSonicBidirectionalStreamClient>();

function getClientForRegion(region: string): NovaSonicBidirectionalStreamClient {
    if (!regionClients.has(region)) {
        console.log(`Creating new Bedrock client for region: ${region}`);
        const client = new NovaSonicBidirectionalStreamClient({
            requestHandlerConfig: {
                maxConcurrentStreams: 10,
            },
            clientConfig: {
                region: region,
                // credentials omitted - SDK default chain only. Never inline keys.
            },
        });
        regionClients.set(region, client);
    }
    return regionClients.get(region)!;
}

const defaultClient = getClientForRegion(YafaConfig.defaultRegion);

// Track active sessions per socket
const socketSessions = new Map<string, StreamSession>();
const socketClients = new Map<string, NovaSonicBidirectionalStreamClient>();
const socketConfigs = new Map<string, any>();

enum SessionState {
    INITIALIZING = 'initializing',
    READY = 'ready',
    ACTIVE = 'active',
    CLOSED = 'closed',
}

const sessionStates = new Map<string, SessionState>();
const cleanupInProgress = new Map<string, boolean>();
const sessionTimers = new Map<string, ReturnType<typeof setTimeout>>();
const connectionsPerSubject = new Map<string, number>();
const connectionLimiter = new FixedWindowRateLimiter(YafaConfig.maxConnectionsPerMinute, 60_000);
const textLimiter = new FixedWindowRateLimiter(YafaConfig.maxTextEventsPerMinute, 60_000);
const audioLimiter = new FixedWindowRateLimiter(YafaConfig.maxAudioEventsPerMinute, 60_000);

function authSubject(socket: any): string {
    return String(socket.data?.authSubject || 'unauthenticated');
}

function clearSessionTimer(socketId: string): void {
    const timer = sessionTimers.get(socketId);
    if (timer) clearTimeout(timer);
    sessionTimers.delete(socketId);
}

function emitSafeError(socket: any, message: string): void {
    socket.emit('error', { message });
}

// Authentication happens before any Bedrock session can be created. Tokens
// are short-lived and signed by the storefront; CORS is only an extra browser
// control and is deliberately not treated as authentication.
io.use((socket, next) => {
    try {
        const address = clientAddress(socket.handshake.address, socket.handshake.headers['x-forwarded-for']);
        let subject = `development:${address}`;
        if (YafaConfig.authRequired) {
            subject = verifyGatewayToken(
                socket.handshake.auth?.token,
                YafaConfig.gatewaySigningSecret,
                YafaConfig.gatewayTokenAudience,
            ).sub;
        }
        if (!connectionLimiter.allow(`ip:${address}`) || !connectionLimiter.allow(`sub:${subject}`)) {
            return next(new Error('rate_limited'));
        }
        if ((connectionsPerSubject.get(subject) || 0) >= YafaConfig.maxConcurrentConnectionsPerUser) {
            return next(new Error('too_many_connections'));
        }
        socket.data.authSubject = subject;
        socket.data.clientAddress = address;
        next();
    } catch {
        next(new Error('unauthorized'));
    }
});

// Close sessions idle for more than 5 minutes (audio billing stops at close).
setInterval(() => {
    const now = Date.now();

    regionClients.forEach((client, region) => {
        client.getActiveSessions().forEach(sessionId => {
            const lastActivity = client.getLastActivityTime(sessionId);
            if (now - lastActivity > 5 * 60 * 1000) {
                console.log(`Closing inactive session ${sessionId} in region ${region}`);
                try {
                    client.forceCloseSession(sessionId);
                } catch (error) {
                    console.error('Error force closing inactive session %s:', sessionId, error);
                }
            }
        });
    });
}, 60000);

async function createNewSession(socket: any): Promise<StreamSession> {
    const sessionId = socket.id;
    // Region, model, inference settings and enabled tools are server-owned.
    // Browser-provided overrides could otherwise expand cost or capabilities.
    const region = YafaConfig.defaultRegion;
    const client = getClientForRegion(region);

    try {
        console.log(`Creating new session for client: ${sessionId} in region: ${region}`);
        sessionStates.set(sessionId, SessionState.INITIALIZING);

        const session = client.createStreamSession(sessionId);
        setupSessionEventHandlers(session, socket);

        socketSessions.set(sessionId, session);
        socketClients.set(sessionId, client);
        socketConfigs.set(sessionId, {});
        sessionStates.set(sessionId, SessionState.READY);

        clearSessionTimer(sessionId);
        sessionTimers.set(sessionId, setTimeout(() => {
            console.log(`Closing session ${sessionId}: hard duration limit reached`);
            try { client.forceCloseSession(sessionId); } catch { /* already closed */ }
            emitSafeError(socket, 'This voice session has reached its time limit. Start a new session to continue.');
            socket.disconnect(true);
        }, YafaConfig.maxSessionMs));

        console.log(`Session ${sessionId} created and ready`);
        return session;
    } catch (error) {
        console.error('Error creating session for %s:', sessionId, error);
        sessionStates.set(sessionId, SessionState.CLOSED);
        throw error;
    }
}

function setupSessionEventHandlers(session: StreamSession, socket: any) {
    session.onEvent('usageEvent', (data) => {
        socket.emit('usageEvent', data);
    });

    session.onEvent('completionStart', (data) => {
        socket.emit('completionStart', data);
    });

    session.onEvent('contentStart', (data) => {
        socket.emit('contentStart', data);
    });

    // textOutput carries both user transcripts and assistant transcripts -
    // the YAFA UI renders these into the chat thread.
    session.onEvent('textOutput', (data) => {
        socket.emit('textOutput', data);
    });

    session.onEvent('audioOutput', (data) => {
        socket.emit('audioOutput', data);
    });

    session.onEvent('error', (data) => {
        console.error('Error in session:', data);
        socket.emit('error', data);
    });

    session.onEvent('toolUse', (data) => {
        socket.emit('toolUse', data);
    });

    session.onEvent('toolResult', (data) => {
        socket.emit('toolResult', data);
    });

    session.onEvent('contentEnd', (data) => {
        socket.emit('contentEnd', data);
    });

    session.onEvent('bargeIn', (data) => {
        socket.emit('bargeIn', data);
    });

    session.onEvent('streamComplete', () => {
        socket.emit('streamComplete');
        sessionStates.set(socket.id, SessionState.CLOSED);
    });

    session.onEvent('streamInterrupted', (data) => {
        socket.emit('streamInterrupted', data);
    });
}

io.on('connection', (socket) => {
    console.log('New client connected:', socket.id);
    const subject = authSubject(socket);
    connectionsPerSubject.set(subject, (connectionsPerSubject.get(subject) || 0) + 1);
    sessionStates.set(socket.id, SessionState.CLOSED);

    // --- session initialization -------------------------------------------------
    socket.on('initializeConnection', async (data?: any, callback?: Function) => {
        try {
            let config: any = {};
            let cb = callback;

            if (typeof data === 'function') {
                cb = data;
            } else if (data && typeof data === 'object') {
                config = data;
            }

            const currentState = sessionStates.get(socket.id);
            if (currentState === SessionState.INITIALIZING || currentState === SessionState.READY || currentState === SessionState.ACTIVE) {
                console.log(`Session already exists for ${socket.id}, state: ${currentState}`);
                if (cb) cb({ success: true });
                return;
            }

            // Client configuration is intentionally ignored; security and
            // inference settings are controlled by the gateway deployment.
            await createNewSession(socket);
            sessionStates.set(socket.id, SessionState.READY);
            if (cb) cb({ success: true });
        } catch (error) {
            console.error('Error initializing session:', error);
            sessionStates.set(socket.id, SessionState.CLOSED);
            const cb = typeof data === 'function' ? data : callback;
            if (cb) cb({ success: false, error: error instanceof Error ? error.message : String(error) });
            emitSafeError(socket, 'Failed to initialize voice session.');
        }
    });

    socket.on('startNewChat', async () => {
        try {
            const existingSession = socketSessions.get(socket.id);
            const client = socketClients.get(socket.id) || defaultClient;

            if (existingSession && client.isSessionActive(socket.id)) {
                console.log(`Cleaning up existing session for ${socket.id}`);
                try {
                    await existingSession.endAudioContent();
                    await existingSession.endPrompt();
                    await existingSession.close();
                } catch (cleanupError) {
                    console.error('Error during cleanup for %s:', socket.id, cleanupError);
                    client.forceCloseSession(socket.id);
                }
                socketSessions.delete(socket.id);
            }

            await createNewSession(socket);
        } catch (error) {
            console.error('Error starting new chat:', error);
            emitSafeError(socket, 'Failed to start a new voice session.');
        }
    });

    // --- voice input ------------------------------------------------------------
    socket.on('audioInput', async (audioData: any) => {
        try {
            const session = socketSessions.get(socket.id);
            const currentState = sessionStates.get(socket.id);

            if (!session || currentState !== SessionState.ACTIVE) {
                emitSafeError(socket, 'No active voice session.');
                return;
            }

            if (!audioLimiter.allow(authSubject(socket))) {
                emitSafeError(socket, 'Voice input rate limit reached. Please pause and try again.');
                return;
            }

            if (
                (typeof audioData === 'string' && audioData.length > Math.ceil(YafaConfig.maxAudioChunkBytes * 4 / 3) + 4) ||
                (typeof audioData !== 'string' && Buffer.byteLength(audioData || []) > YafaConfig.maxAudioChunkBytes)
            ) {
                emitSafeError(socket, 'Voice input chunk is too large.');
                return;
            }

            const audioBuffer = typeof audioData === 'string'
                ? Buffer.from(audioData, 'base64')
                : Buffer.from(audioData);

            if (audioBuffer.byteLength > YafaConfig.maxAudioChunkBytes) {
                emitSafeError(socket, 'Voice input chunk is too large.');
                return;
            }

            await session.streamAudio(audioBuffer);
        } catch (error) {
            console.error('Error processing audio:', error);
            emitSafeError(socket, 'Voice input could not be processed.');
        }
    });

    // Setup sequence: promptStart -> systemPrompt -> audioStart -> ACTIVE.
    socket.on('promptStart', async (data?: any) => {
        try {
            const session = socketSessions.get(socket.id);
            if (!session) {
                socket.emit('error', { message: 'No active session for prompt start' });
                return;
            }
            const voiceId = YafaConfig.voiceId;
            const outputSampleRate = 24000;
            await session.setupSessionAndPromptStart(voiceId, outputSampleRate);
            console.log(`Prompt start completed for ${socket.id} with sample rate ${outputSampleRate}`);
        } catch (error) {
            console.error('Error processing prompt start:', error);
            emitSafeError(socket, 'Voice prompt could not be started.');
        }
    });

    socket.on('systemPrompt', async () => {
        try {
            const session = socketSessions.get(socket.id);
            if (!session) {
                socket.emit('error', { message: 'No active session for system prompt' });
                return;
            }

            // The client cannot append instructions to the system prompt.
            await session.setupSystemPrompt(undefined, YAFA_SYSTEM_PROMPT);
            console.log(`System prompt completed for ${socket.id}`);
        } catch (error) {
            console.error('Error processing system prompt:', error);
            emitSafeError(socket, 'Voice assistant instructions could not be loaded.');
        }
    });

    socket.on('audioStart', async () => {
        try {
            const session = socketSessions.get(socket.id);
            if (!session) {
                socket.emit('error', { message: 'No active session for audio start' });
                return;
            }

            await session.setupStartAudio();
            console.log(`Audio start setup completed for ${socket.id}`);

            // All setup events are queued - NOW open the Bedrock stream.
            const client = socketClients.get(socket.id) || defaultClient;
            client.initiateBidirectionalStreaming(socket.id);

            sessionStates.set(socket.id, SessionState.ACTIVE);
            socket.emit('audioReady');
        } catch (error) {
            console.error('Error processing audio start:', error);
            sessionStates.set(socket.id, SessionState.CLOSED);
            emitSafeError(socket, 'Voice stream could not be started.');
        }
    });

    // --- typed input through the SAME pipeline ----------------------------------
    socket.on('textInput', async (data: any) => {
        try {
            const session = socketSessions.get(socket.id);
            if (!session) {
                socket.emit('error', { message: 'No active session for text input' });
                return;
            }

            const client = socketClients.get(socket.id) || defaultClient;
            const currentState = sessionStates.get(socket.id);

            if (currentState === SessionState.READY) {
                client.initiateBidirectionalStreaming(socket.id);
                sessionStates.set(socket.id, SessionState.ACTIVE);
            }

            if (!textLimiter.allow(authSubject(socket))) {
                emitSafeError(socket, 'Message rate limit reached. Please wait before trying again.');
                return;
            }
            const content = validateCustomerText(
                typeof data === 'string' ? data : data?.content,
                YafaConfig.maxTextChars,
            );
            if (!content) {
                emitSafeError(socket, 'That message cannot be processed. Please ask a concise beauty or YAFA VANAM question.');
                return;
            }
            await session.sendTextInput(content);
        } catch (error) {
            console.error('Error processing text input:', error);
            emitSafeError(socket, 'That message could not be processed.');
        }
    });

    // --- teardown -----------------------------------------------------------------
    socket.on('stopAudio', async () => {
        try {
            const session = socketSessions.get(socket.id);
            const client = socketClients.get(socket.id) || defaultClient;

            if (!session || cleanupInProgress.get(socket.id)) {
                socket.emit('sessionClosed');
                return;
            }

            cleanupInProgress.set(socket.id, true);
            sessionStates.set(socket.id, SessionState.CLOSED);

            const cleanupPromise = Promise.race([
                (async () => {
                    await session.endAudioContent();
                    await session.endPrompt();
                    await session.close();
                })(),
                new Promise((_, reject) =>
                    setTimeout(() => reject(new Error('Session cleanup timeout')), 5000)
                ),
            ]);

            await cleanupPromise;

            socketSessions.delete(socket.id);
            socketClients.delete(socket.id);
            socketConfigs.delete(socket.id);
            cleanupInProgress.delete(socket.id);
            clearSessionTimer(socket.id);

            socket.emit('sessionClosed');
        } catch (error) {
            console.error('Error processing streaming end events:', error);

            try {
                const client = socketClients.get(socket.id) || defaultClient;
                client.forceCloseSession(socket.id);
                socketSessions.delete(socket.id);
                socketClients.delete(socket.id);
                socketConfigs.delete(socket.id);
                cleanupInProgress.delete(socket.id);
                sessionStates.set(socket.id, SessionState.CLOSED);
            } catch (forceError) {
                console.error('Error during force cleanup:', forceError);
            }

            socket.emit('sessionClosed');
            socket.emit('error', {
                message: 'Error processing streaming end events',
                details: error instanceof Error ? error.message : String(error),
            });
        }
    });

    socket.on('disconnect', async () => {
        console.log('Client disconnected:', socket.id);

        const session = socketSessions.get(socket.id);
        const client = socketClients.get(socket.id) || defaultClient;
        const sessionId = socket.id;

        if (session && client.isSessionActive(sessionId) && !cleanupInProgress.get(socket.id)) {
            try {
                cleanupInProgress.set(socket.id, true);

                const cleanupPromise = Promise.race([
                    (async () => {
                        await session.endAudioContent();
                        await session.endPrompt();
                        await session.close();
                    })(),
                    new Promise((_, reject) =>
                        setTimeout(() => reject(new Error('Session cleanup timeout')), 3000)
                    ),
                ]);

                await cleanupPromise;
            } catch (error) {
                console.error('Error cleaning up session %s:', socket.id, error);
                try {
                    client.forceCloseSession(sessionId);
                } catch (e) {
                    console.error('Failed force close for session: %s', sessionId, e);
                }
            }
        }

        socketSessions.delete(socket.id);
        socketClients.delete(socket.id);
        socketConfigs.delete(socket.id);
        sessionStates.delete(socket.id);
        cleanupInProgress.delete(socket.id);
        clearSessionTimer(socket.id);
        const remaining = Math.max(0, (connectionsPerSubject.get(subject) || 1) - 1);
        if (remaining === 0) connectionsPerSubject.delete(subject);
        else connectionsPerSubject.set(subject, remaining);
    });
});

app.get('/api/tools', (_req, res) => {
    const toolSpecs = defaultClient.getToolRegistry().getToolSpecs();
    res.status(200).json({
        tools: toolSpecs.map(t => ({ name: t.toolSpec.name, description: t.toolSpec.description })),
    });
});

app.get('/health', (_req, res) => {
    res.status(200).json({
        status: 'ok',
        service: 'yafa-voice-gateway',
        model: YafaConfig.modelId,
        region: YafaConfig.defaultRegion,
        timestamp: new Date().toISOString(),
        activeSessions: Array.from(regionClients.values()).reduce((n, c) => n + c.getActiveSessions().length, 0),
        socketConnections: Object.keys(io.sockets.sockets).length,
    });
});

server.listen(Number(YafaConfig.port), YafaConfig.host, () => {
    console.log(`Yafa voice gateway listening on ${YafaConfig.host}:${YafaConfig.port}`);
    console.log(`Model: ${YafaConfig.modelId} | Region: ${YafaConfig.defaultRegion} | Voice: ${YafaConfig.voiceId}`);
    console.log(`Allowed origins: ${YafaConfig.allowedOrigins.join(', ')}`);
});

process.on('SIGINT', async () => {
    console.log('Shutting down voice gateway...');

    const forceExitTimer = setTimeout(() => {
        console.error('Forcing server shutdown after timeout');
        process.exit(1);
    }, 5000);

    try {
        await new Promise(resolve => io.close(resolve));

        for (const [region, client] of regionClients) {
            const activeSessions = client.getActiveSessions();
            console.log(`Closing ${activeSessions.length} sessions in region ${region}...`);
            await Promise.all(activeSessions.map(async (sessionId) => {
                try {
                    await client.closeSession(sessionId);
                } catch (error) {
                    console.error('Error closing session %s:', sessionId, error);
                    client.forceCloseSession(sessionId);
                }
            }));
        }

        await new Promise(resolve => server.close(resolve));
        clearTimeout(forceExitTimer);
        console.log('Server shut down');
        process.exit(0);
    } catch (error) {
        console.error('Error during server shutdown:', error);
        process.exit(1);
    }
});
