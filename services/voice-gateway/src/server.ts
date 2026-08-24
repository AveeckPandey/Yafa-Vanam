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

async function createNewSession(socket: any, config: any = {}): Promise<StreamSession> {
    const sessionId = socket.id;
    const region = config.region || YafaConfig.defaultRegion;
    const client = getClientForRegion(region);

    try {
        console.log(`Creating new session for client: ${sessionId} in region: ${region}`);
        sessionStates.set(sessionId, SessionState.INITIALIZING);

        const sessionConfig: any = {};

        if (config.inferenceConfig) {
            sessionConfig.inferenceConfig = {
                maxTokens: config.inferenceConfig.maxTokens || 2048,
                topP: config.inferenceConfig.topP || 0.9,
                temperature: config.inferenceConfig.temperature || 1,
            };
        }

        if (config.turnDetectionConfig?.endpointingSensitivity) {
            sessionConfig.turnDetectionConfig = {
                endpointingSensitivity: config.turnDetectionConfig.endpointingSensitivity,
            };
        }

        if (config.enabledTools && Array.isArray(config.enabledTools)) {
            sessionConfig.enabledTools = config.enabledTools;
        }

        const session = client.createStreamSession(sessionId, Object.keys(sessionConfig).length > 0 ? sessionConfig : undefined);
        setupSessionEventHandlers(session, socket);

        socketSessions.set(sessionId, session);
        socketClients.set(sessionId, client);
        socketConfigs.set(sessionId, config);
        sessionStates.set(sessionId, SessionState.READY);

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

            await createNewSession(socket, config);
            sessionStates.set(socket.id, SessionState.READY);
            if (cb) cb({ success: true });
        } catch (error) {
            console.error('Error initializing session:', error);
            sessionStates.set(socket.id, SessionState.CLOSED);
            const cb = typeof data === 'function' ? data : callback;
            if (cb) cb({ success: false, error: error instanceof Error ? error.message : String(error) });
            socket.emit('error', {
                message: 'Failed to initialize session',
                details: error instanceof Error ? error.message : String(error),
            });
        }
    });

    socket.on('startNewChat', async (config: any = {}) => {
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

            await createNewSession(socket, config);
        } catch (error) {
            console.error('Error starting new chat:', error);
            socket.emit('error', {
                message: 'Failed to start new chat',
                details: error instanceof Error ? error.message : String(error),
            });
        }
    });

    // --- voice input ------------------------------------------------------------
    socket.on('audioInput', async (audioData: any) => {
        try {
            const session = socketSessions.get(socket.id);
            const currentState = sessionStates.get(socket.id);

            if (!session || currentState !== SessionState.ACTIVE) {
                socket.emit('error', {
                    message: 'No active session for audio input',
                    details: `Session exists: ${!!session}, Session state: ${currentState}.`,
                });
                return;
            }

            const audioBuffer = typeof audioData === 'string'
                ? Buffer.from(audioData, 'base64')
                : Buffer.from(audioData);

            await session.streamAudio(audioBuffer);
        } catch (error) {
            console.error('Error processing audio:', error);
            socket.emit('error', {
                message: 'Error processing audio',
                details: error instanceof Error ? error.message : String(error),
            });
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
            const voiceId = data?.voiceId || YafaConfig.voiceId;
            const outputSampleRate = data?.outputSampleRate || 24000;
            await session.setupSessionAndPromptStart(voiceId, outputSampleRate);
            console.log(`Prompt start completed for ${socket.id} with sample rate ${outputSampleRate}`);
        } catch (error) {
            console.error('Error processing prompt start:', error);
            socket.emit('error', {
                message: 'Error processing prompt start',
                details: error instanceof Error ? error.message : String(error),
            });
        }
    });

    socket.on('systemPrompt', async (data: any) => {
        try {
            const session = socketSessions.get(socket.id);
            if (!session) {
                socket.emit('error', { message: 'No active session for system prompt' });
                return;
            }

            // The gateway owns Yafa's personality; a client MAY extend it with
            // extra context appended after the base prompt.
            const base = YAFA_SYSTEM_PROMPT;
            const extra = typeof data?.extraContext === 'string' ? data.extraContext.trim() : '';
            const content = extra ? `${base}\n\nSESSION CONTEXT:\n${extra}` : base;

            await session.setupSystemPrompt(undefined, content);
            console.log(`System prompt completed for ${socket.id}`);
        } catch (error) {
            console.error('Error processing system prompt:', error);
            socket.emit('error', {
                message: 'Error processing system prompt',
                details: error instanceof Error ? error.message : String(error),
            });
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
            socket.emit('error', {
                message: 'Error processing audio start',
                details: error instanceof Error ? error.message : String(error),
            });
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

            const content = typeof data === 'string' ? data : data?.content;
            await session.sendTextInput(content);
        } catch (error) {
            console.error('Error processing text input:', error);
            socket.emit('error', {
                message: 'Error processing text input',
                details: error instanceof Error ? error.message : String(error),
            });
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
