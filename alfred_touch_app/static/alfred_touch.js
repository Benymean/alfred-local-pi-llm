const body = document.body;
const assistantName = body.dataset.assistantName || "Alfred";

const homeScreen = document.getElementById("home-screen");
const chatScreen = document.getElementById("chat-screen");
const settingsScreen = document.getElementById("settings-screen");
const healthScreen = document.getElementById("health-screen");
const screens = {
    home: homeScreen,
    chat: chatScreen,
    settings: settingsScreen,
    health: healthScreen,
};

const chatOpenButton = document.getElementById("chat-open");
const chatBackButton = document.getElementById("chat-back");
const settingsOpenButton = document.getElementById("settings-open");
const settingsBackButton = document.getElementById("settings-back");
const openHealthButton = document.getElementById("open-health");
const healthBackButton = document.getElementById("health-back");

const chatHistory = document.getElementById("chat-history");
const composer = document.getElementById("composer");
const userInput = document.getElementById("user-input");
const sendButton = document.getElementById("send-button");
const clearScreenButton = document.getElementById("clear-screen");

const micButton = document.getElementById("mic-button");
const stopSpeakingButton = document.getElementById("stop-speaking");
const faceTranscript = document.getElementById("face-transcript");
const stateLabel = document.getElementById("state-label");
const statusPill = document.getElementById("status-pill");
const statusText = document.getElementById("status-text");

const voiceToggle = document.getElementById("voice-toggle");
const settingsModel = document.getElementById("settings-model");
const resetMemoryButton = document.getElementById("reset-memory");
const restartBackendButton = document.getElementById("restart-backend");
const testSpeakerButton = document.getElementById("test-speaker");
const testMicrophoneButton = document.getElementById("test-microphone");

const healthUpdated = document.getElementById("health-updated");
const healthBackend = document.getElementById("health-backend");
const healthModel = document.getElementById("health-model");
const healthStt = document.getElementById("health-stt");
const healthTts = document.getElementById("health-tts");
const healthMic = document.getElementById("health-mic");
const healthSpeaker = document.getElementById("health-speaker");
const healthLastError = document.getElementById("health-last-error");
const faceCanvas = document.getElementById("alfred-face");

const defaultIdlePrompt = "Tap to talk.";

let activeScreen = "home";
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let currentRecordingMode = "chat";
let recordingAutoStopTimer = null;
let currentAudio = null;
let currentAudioContext = null;
let currentAnalyser = null;
let currentDataArray = null;
let queuedAudioSegments = [];
let audioQueueDrainResolvers = [];
let lastServerHealth = null;
let micPermissionStatus = "Checking permission";
let micDiagnosticStatus = "Not tested";
let speakerDiagnosticStatus = typeof Audio === "undefined" ? "Browser audio unavailable" : "Ready to test";
let uiLastIssue = "";
let currentTurnMeta = null;
let activeVoiceStreamController = null;

class AlfredFaceRenderer {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext("2d");
        this.state = "idle";
        this.frame = 0;
        this.blink = 0;
        this.mouthOpen = 0;
        this.eyeDrift = 0;
        this.eyeLift = 0;
        this.dotsOffset = 0;
        this.render = this.render.bind(this);
    }

    setState(nextState) {
        this.state = nextState;
        if (nextState !== "speaking") {
            this.mouthOpen = 0;
        }
    }

    render() {
        const { ctx } = this;
        const width = this.canvas.width;
        const height = this.canvas.height;
        const centerX = width / 2;
        const centerY = height / 2;
        this.frame += 1;

        ctx.clearRect(0, 0, width, height);
        this._background(ctx, width, height);

        this.blink = this._blinkAmount();
        this.eyeDrift = Math.sin(this.frame * 0.015) * 10;
        this.eyeLift = Math.cos(this.frame * 0.01) * 4;
        this.dotsOffset = (this.frame * 3) % 110;

        this._drawHalo(ctx, centerX, centerY);
        this._drawFacePlate(ctx, centerX, centerY);
        this._drawEyes(ctx, centerX, centerY);
        this._drawMouth(ctx, centerX, centerY + 70);
        this._drawOrnaments(ctx, width, height);

        requestAnimationFrame(this.render);
    }

    _background(ctx, width, height) {
        const gradient = ctx.createLinearGradient(0, 0, 0, height);
        gradient.addColorStop(0, "#f7eef4");
        gradient.addColorStop(0.5, "#f0e7ee");
        gradient.addColorStop(1, "#e8edf3");
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, width, height);

        const bloom = ctx.createRadialGradient(width * 0.5, height * 0.3, 40, width * 0.5, height * 0.42, 320);
        bloom.addColorStop(0, "rgba(255, 255, 255, 0.72)");
        bloom.addColorStop(1, "rgba(255, 255, 255, 0)");
        ctx.fillStyle = bloom;
        ctx.fillRect(0, 0, width, height);
    }

    _drawHalo(ctx, centerX, centerY) {
        const haloGlow = ctx.createRadialGradient(centerX, centerY - 12, 48, centerX, centerY + 12, 240);
        haloGlow.addColorStop(0, "rgba(59, 243, 233, 0.18)");
        haloGlow.addColorStop(1, "rgba(59, 243, 233, 0)");
        ctx.fillStyle = haloGlow;
        ctx.beginPath();
        ctx.arc(centerX, centerY + 18, 230, 0, Math.PI * 2);
        ctx.fill();

        ctx.save();
        ctx.strokeStyle = "rgba(255, 255, 255, 0.58)";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(centerX - 138, centerY - 118);
        ctx.quadraticCurveTo(centerX - 122, centerY - 196, centerX - 54, centerY - 206);
        ctx.moveTo(centerX + 138, centerY - 118);
        ctx.quadraticCurveTo(centerX + 122, centerY - 196, centerX + 54, centerY - 206);
        ctx.stroke();
        ctx.restore();

        ctx.save();
        ctx.translate(centerX, centerY - 204);
        ctx.rotate(-0.03);

        ctx.strokeStyle = "rgba(255, 255, 255, 0.9)";
        ctx.lineWidth = 9;
        ctx.shadowColor = "rgba(88, 245, 236, 0.18)";
        ctx.shadowBlur = 24;
        ctx.beginPath();
        ctx.ellipse(0, 0, 82, 24, 0, 0, Math.PI * 2);
        ctx.stroke();

        ctx.shadowBlur = 16;
        ctx.strokeStyle = "#caa66c";
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.ellipse(0, 0, 72, 18, 0, 0, Math.PI * 2);
        ctx.stroke();

        ctx.strokeStyle = "#63f4ef";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.ellipse(10, 0, 48, 10, 0, Math.PI * 1.08, Math.PI * 1.95);
        ctx.stroke();
        ctx.restore();
    }

    _drawFacePlate(ctx, centerX, centerY) {
        ctx.save();
        ctx.translate(centerX, centerY);

        ctx.fillStyle = "rgba(26, 23, 28, 0.12)";
        ctx.beginPath();
        ctx.ellipse(0, 162, 170, 32, 0, 0, Math.PI * 2);
        ctx.fill();

        this._drawSidePod(ctx, -206, 8, "left");
        this._drawSidePod(ctx, 206, 8, "right");

        const shellGradient = ctx.createLinearGradient(0, -170, 0, 170);
        shellGradient.addColorStop(0, "#fff8ef");
        shellGradient.addColorStop(0.52, "#f4e5d1");
        shellGradient.addColorStop(1, "#e1c8a5");
        ctx.fillStyle = shellGradient;
        ctx.strokeStyle = "#d5aa69";
        ctx.lineWidth = 6;
        this._shellPath(ctx);
        ctx.fill();
        ctx.stroke();

        ctx.strokeStyle = "rgba(255, 255, 255, 0.88)";
        ctx.lineWidth = 2.5;
        this._shellPath(ctx, 10);
        ctx.stroke();

        const screenGlow = ctx.createRadialGradient(0, -8, 30, 0, -4, 220);
        screenGlow.addColorStop(0, "rgba(60, 247, 238, 0.16)");
        screenGlow.addColorStop(1, "rgba(60, 247, 238, 0)");
        ctx.fillStyle = screenGlow;
        ctx.beginPath();
        ctx.arc(0, -4, 200, 0, Math.PI * 2);
        ctx.fill();

        const screenGradient = ctx.createLinearGradient(0, -116, 0, 130);
        screenGradient.addColorStop(0, "#11171c");
        screenGradient.addColorStop(0.62, "#090d12");
        screenGradient.addColorStop(1, "#0d171d");
        ctx.fillStyle = screenGradient;
        ctx.strokeStyle = "#c59a5b";
        ctx.lineWidth = 5;
        this._screenPath(ctx);
        ctx.fill();
        ctx.stroke();

        ctx.save();
        this._screenPath(ctx);
        ctx.clip();
        const gloss = ctx.createLinearGradient(0, -120, 0, 40);
        gloss.addColorStop(0, "rgba(255, 255, 255, 0.2)");
        gloss.addColorStop(1, "rgba(255, 255, 255, 0)");
        ctx.fillStyle = gloss;
        ctx.beginPath();
        ctx.ellipse(-36, -96, 178, 78, -0.12, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

        const crestGradient = ctx.createLinearGradient(0, -182, 0, -124);
        crestGradient.addColorStop(0, "#fff8ef");
        crestGradient.addColorStop(1, "#f0dbc0");
        ctx.fillStyle = crestGradient;
        ctx.strokeStyle = "#d5aa69";
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(-34, -144);
        ctx.quadraticCurveTo(0, -178, 34, -144);
        ctx.quadraticCurveTo(16, -124, 0, -118);
        ctx.quadraticCurveTo(-16, -124, -34, -144);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = "#b6844c";
        ctx.beginPath();
        ctx.arc(0, -148, 6, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = "rgba(255, 255, 255, 0.48)";
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(-126, -114);
        ctx.quadraticCurveTo(-44, -138, 0, -132);
        ctx.stroke();
        ctx.restore();
    }

    _drawEyes(ctx, centerX, centerY) {
        if (this.state === "thinking") {
            this._drawThinkingEyes(ctx, centerX, centerY);
            return;
        }

        const leftX = centerX - 82 + this.eyeDrift * 0.5;
        const rightX = centerX + 78 + this.eyeDrift * 0.5;
        const eyeY = centerY - 18 + this.eyeLift * 0.45;
        const lifted = this.state === "listening" ? -6 : 0;
        const pupilOffset = this.state === "listening" ? Math.sin(this.frame * 0.08) * 3 : 0;
        const speakingBob = this.state === "speaking" ? Math.sin(this.frame * 0.14) * 1.5 : 0;
        const leftBrowTilt = this.state === "error" ? 0.34 : (this.state === "speaking" ? 0.06 : 0.18);
        const rightBrowTilt = this.state === "error" ? -0.34 : (this.state === "speaking" ? -0.06 : -0.18);

        this._drawBrow(ctx, leftX, eyeY - 58 + lifted, 42, leftBrowTilt);
        this._drawBrow(ctx, rightX, eyeY - 58 + lifted, 36, rightBrowTilt);
        this._drawEye(ctx, leftX, eyeY + lifted, 1, pupilOffset + speakingBob, 0, this.state === "speaking" ? 0.96 : 1);
        this._drawEye(ctx, rightX, eyeY + lifted, 0.92, pupilOffset + speakingBob, 0, this.state === "speaking" ? 0.96 : 1);

        if (this.state === "listening") {
            ctx.save();
            ctx.strokeStyle = "rgba(84, 244, 236, 0.42)";
            ctx.lineWidth = 6;
            ctx.shadowColor = "rgba(84, 244, 236, 0.22)";
            ctx.shadowBlur = 18;
            ctx.beginPath();
            ctx.ellipse(centerX, centerY - 6, 146 + Math.sin(this.frame * 0.12) * 6, 110 + Math.sin(this.frame * 0.1) * 6, 0, 0, Math.PI * 2);
            ctx.stroke();
            ctx.restore();
        }
    }

    _drawEye(ctx, x, y, scale = 1, pupilOffsetX = 0, pupilOffsetY = 0, verticalSquash = 1) {
        ctx.save();
        if (this.blink > 0.86) {
            this._drawClosedEye(ctx, x, y + 2, 36 * scale, 0.14 * scale);
            ctx.restore();
            return;
        }

        if (this.state === "error") {
            this._drawClosedEye(ctx, x, y + 6, 34 * scale, scale > 0.95 ? -0.28 : 0.28);
            ctx.restore();
            return;
        }

        ctx.shadowColor = "rgba(74, 247, 239, 0.4)";
        ctx.shadowBlur = 18;

        const outerWidth = 48 * scale;
        const outerHeight = 62 * scale * verticalSquash;
        const innerOffsetX = 6 * scale + pupilOffsetX;
        const innerOffsetY = pupilOffsetY;

        const outerGradient = ctx.createRadialGradient(x, y - 6, 6, x, y, outerWidth);
        outerGradient.addColorStop(0, "#b4fff7");
        outerGradient.addColorStop(0.45, "#62f5ef");
        outerGradient.addColorStop(1, "#1bb4b7");
        ctx.fillStyle = outerGradient;
        ctx.beginPath();
        ctx.ellipse(x, y, outerWidth, outerHeight, -0.06, 0, Math.PI * 2);
        ctx.fill();

        ctx.shadowBlur = 0;
        ctx.fillStyle = "#05090c";
        ctx.beginPath();
        ctx.ellipse(x + innerOffsetX, y + 2 + innerOffsetY, outerWidth * 0.46, outerHeight * 0.58, -0.02, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = "rgba(164, 255, 248, 0.92)";
        ctx.beginPath();
        ctx.arc(x - outerWidth * 0.24, y - outerHeight * 0.18 + innerOffsetY * 0.25, 8 * scale, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = "rgba(98, 245, 239, 0.86)";
        ctx.beginPath();
        ctx.arc(x - outerWidth * 0.06, y + outerHeight * 0.18, 5 * scale, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    }

    _drawThinkingEyes(ctx, centerX, centerY) {
        const leftX = centerX - 82 + this.eyeDrift * 0.18;
        const rightX = centerX + 78 + this.eyeDrift * 0.18;
        const eyeY = centerY - 14;
        const glanceX = 10 + Math.sin(this.frame * 0.08) * 2.5;
        const glanceY = -4 + Math.cos(this.frame * 0.07) * 1.6;

        this._drawBrow(ctx, leftX, eyeY - 60, 44, -0.16);
        this._drawBrow(ctx, rightX, eyeY - 55, 34, 0.32);

        this._drawEye(ctx, leftX, eyeY, 0.96, glanceX, glanceY, 0.93);
        this._drawEye(ctx, rightX, eyeY + 2, 0.76, glanceX * 0.65, glanceY + 2, 0.84);

        ctx.save();
        ctx.strokeStyle = "#60f7ef";
        ctx.lineWidth = 3.5;
        ctx.lineCap = "round";
        ctx.shadowColor = "rgba(96, 247, 239, 0.42)";
        ctx.shadowBlur = 14;
        const orbitX = centerX + 130 + Math.sin(this.frame * 0.08) * 4;
        const orbitY = centerY - 20;
        ctx.beginPath();
        ctx.arc(orbitX, orbitY, 14, Math.PI * 1.25, Math.PI * 0.58, true);
        ctx.stroke();

        const dotBaseX = centerX + 110 + Math.sin(this.frame * 0.05) * 5;
        for (let index = 0; index < 3; index += 1) {
            ctx.fillStyle = index === 1 ? "#b4fff7" : "#60f7ef";
            ctx.beginPath();
            ctx.arc(dotBaseX + index * 18, centerY + 8 + Math.sin(this.frame * 0.1 + index) * 2, 4.5, 0, Math.PI * 2);
            ctx.fill();
        }
        ctx.restore();
    }

    _drawMouth(ctx, centerX, mouthY) {
        ctx.save();
        ctx.strokeStyle = "#63f4ef";
        ctx.fillStyle = "#63f4ef";
        ctx.lineWidth = 6;
        ctx.lineCap = "round";
        ctx.shadowColor = "rgba(99, 244, 239, 0.36)";
        ctx.shadowBlur = 16;

        if (this.state === "thinking") {
            this._drawThinkingMouth(ctx, centerX + 6, mouthY + 2);
            ctx.restore();
            return;
        }

        if (this.state === "listening") {
            ctx.beginPath();
            ctx.arc(centerX, mouthY - 2, 22, 0.1 * Math.PI, 0.9 * Math.PI, false);
            ctx.stroke();
            ctx.restore();
            return;
        }

        if (this.state === "error") {
            ctx.beginPath();
            ctx.arc(centerX, mouthY + 20, 16, 1.18 * Math.PI, 1.82 * Math.PI, false);
            ctx.stroke();
            ctx.restore();
            return;
        }

        if (this.state === "speaking") {
            this._drawSpeakingMouth(ctx, centerX, mouthY - 2);
            ctx.restore();
            return;
        }

        ctx.beginPath();
        ctx.arc(centerX, mouthY - 10, 18, 0.12 * Math.PI, 0.88 * Math.PI, false);
        ctx.stroke();
        ctx.restore();
    }

    _drawOrnaments(ctx, width, height) {
        ctx.save();
        ctx.strokeStyle = "rgba(255, 255, 255, 0.5)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(width * 0.16, height * 0.28);
        ctx.lineTo(width * 0.145, height * 0.305);
        ctx.moveTo(width * 0.16, height * 0.28);
        ctx.lineTo(width * 0.185, height * 0.305);
        ctx.moveTo(width * 0.16, height * 0.28);
        ctx.lineTo(width * 0.16, height * 0.25);
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(width * 0.84, height * 0.3);
        ctx.lineTo(width * 0.825, height * 0.325);
        ctx.moveTo(width * 0.84, height * 0.3);
        ctx.lineTo(width * 0.865, height * 0.325);
        ctx.moveTo(width * 0.84, height * 0.3);
        ctx.lineTo(width * 0.84, height * 0.27);
        ctx.stroke();
        ctx.restore();
    }

    _drawThinkingMouth(ctx, x, y) {
        ctx.save();
        ctx.strokeStyle = "#63f4ef";
        ctx.lineWidth = 5.5;
        ctx.lineCap = "round";
        ctx.shadowColor = "rgba(99, 244, 239, 0.36)";
        ctx.shadowBlur = 14;
        ctx.beginPath();
        ctx.moveTo(x - 12, y + 4);
        ctx.quadraticCurveTo(x - 1, y - 6, x + 11, y + 1);
        ctx.stroke();
        ctx.restore();
    }

    _drawSpeakingMouth(ctx, x, y) {
        const open = Math.max(12, Math.min(28, this.mouthOpen * 0.72));
        const width = 42 + Math.min(12, open * 0.3);
        const smileLift = 4 + Math.sin(this.frame * 0.18) * 1.2;

        ctx.save();
        ctx.fillStyle = "rgba(104, 246, 239, 0.18)";
        ctx.beginPath();
        ctx.ellipse(x, y + 2, width * 0.7, open * 1.1, 0, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = "#071116";
        ctx.strokeStyle = "#68f6ef";
        ctx.lineWidth = 4.5;
        ctx.shadowColor = "rgba(104, 246, 239, 0.34)";
        ctx.shadowBlur = 14;
        ctx.beginPath();
        ctx.moveTo(x - width * 0.5, y - 3);
        ctx.quadraticCurveTo(x, y + open + smileLift, x + width * 0.5, y - 3);
        ctx.quadraticCurveTo(x, y + open * 0.14, x - width * 0.5, y - 3);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();

        ctx.strokeStyle = "rgba(182, 255, 249, 0.9)";
        ctx.lineWidth = 2.5;
        ctx.shadowBlur = 0;
        ctx.beginPath();
        ctx.arc(x, y - 2, Math.max(6, width * 0.16), Math.PI * 0.16, Math.PI * 0.84, false);
        ctx.stroke();
        ctx.restore();
    }

    _drawSidePod(ctx, x, y, side) {
        ctx.save();
        ctx.translate(x, y);

        const podGradient = ctx.createLinearGradient(0, -48, 0, 48);
        podGradient.addColorStop(0, "#fbf4eb");
        podGradient.addColorStop(1, "#e0c49e");
        ctx.fillStyle = podGradient;
        ctx.strokeStyle = "#c99d5d";
        ctx.lineWidth = 5;
        ctx.beginPath();
        ctx.arc(0, 0, 44, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = "#6ff7ef";
        ctx.globalAlpha = 0.18;
        ctx.beginPath();
        ctx.arc(side === "left" ? 8 : -8, 0, 20, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 1;

        ctx.strokeStyle = "#6cf6ef";
        ctx.lineWidth = 4;
        ctx.shadowColor = "rgba(108, 246, 239, 0.34)";
        ctx.shadowBlur = 12;
        ctx.beginPath();
        ctx.arc(side === "left" ? 7 : -7, 0, 14, -Math.PI * 0.5, Math.PI * 0.5, side === "left");
        ctx.stroke();
        ctx.restore();
    }

    _drawBrow(ctx, x, y, width, tilt = 0) {
        ctx.save();
        ctx.strokeStyle = "#62f5ef";
        ctx.lineWidth = 6;
        ctx.lineCap = "round";
        ctx.shadowColor = "rgba(98, 245, 239, 0.38)";
        ctx.shadowBlur = 14;
        ctx.beginPath();
        ctx.moveTo(x - width * 0.52, y + tilt * 12);
        ctx.quadraticCurveTo(x, y - 12 - Math.abs(tilt) * 10, x + width * 0.52, y - tilt * 12);
        ctx.stroke();
        ctx.restore();
    }

    _drawClosedEye(ctx, x, y, width, tilt = 0) {
        ctx.save();
        ctx.strokeStyle = "#62f5ef";
        ctx.lineWidth = 7;
        ctx.lineCap = "round";
        ctx.shadowColor = "rgba(98, 245, 239, 0.4)";
        ctx.shadowBlur = 14;
        ctx.beginPath();
        ctx.moveTo(x - width * 0.5, y + tilt * 14);
        ctx.quadraticCurveTo(x, y - 8, x + width * 0.5, y - tilt * 14);
        ctx.stroke();
        ctx.restore();
    }

    _shellPath(ctx, inset = 0) {
        const left = -188 + inset;
        const top = -152 + inset;
        const right = 188 - inset;
        const bottom = 160 - inset;
        ctx.beginPath();
        ctx.moveTo(left + 72, top + 18);
        ctx.quadraticCurveTo(left + 24, top + 12, left + 16, top + 76);
        ctx.lineTo(left + 12, bottom - 60);
        ctx.quadraticCurveTo(left + 20, bottom - 6, left + 84, bottom - 4);
        ctx.lineTo(right - 84, bottom - 4);
        ctx.quadraticCurveTo(right - 20, bottom - 6, right - 12, bottom - 60);
        ctx.lineTo(right - 16, top + 76);
        ctx.quadraticCurveTo(right - 24, top + 12, right - 72, top + 18);
        ctx.quadraticCurveTo(0, top - 18, left + 72, top + 18);
        ctx.closePath();
        return ctx;
    }

    _screenPath(ctx) {
        const x = -158;
        const y = -108;
        const width = 316;
        const height = 226;
        const radius = 64;

        ctx.beginPath();
        ctx.moveTo(x + radius, y + 8);
        ctx.lineTo(x + width / 2 - 44, y + 8);
        ctx.quadraticCurveTo(x + width / 2, y + 30, x + width / 2 + 44, y + 8);
        ctx.lineTo(x + width - radius, y + 8);
        ctx.quadraticCurveTo(x + width, y + 8, x + width, y + radius + 8);
        ctx.lineTo(x + width, y + height - radius);
        ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
        ctx.lineTo(x + radius, y + height);
        ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
        ctx.lineTo(x, y + radius + 8);
        ctx.quadraticCurveTo(x, y + 8, x + radius, y + 8);
        ctx.closePath();
        return ctx;
    }

    _blinkAmount() {
        if (this.state === "thinking") {
            return 0;
        }
        const cycle = this.frame % 210;
        if (cycle < 8) {
            return 1;
        }
        if (cycle < 14) {
            return 0.45;
        }
        return 0;
    }

    _roundedRect(ctx, x, y, width, height, radius) {
        ctx.beginPath();
        ctx.moveTo(x + radius, y);
        ctx.lineTo(x + width - radius, y);
        ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
        ctx.lineTo(x + width, y + height - radius);
        ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
        ctx.lineTo(x + radius, y + height);
        ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
        ctx.lineTo(x, y + radius);
        ctx.quadraticCurveTo(x, y, x + radius, y);
        ctx.closePath();
    }
}

const faceRenderer = new AlfredFaceRenderer(faceCanvas);
faceRenderer.render();

function showScreen(name) {
    activeScreen = name;
    Object.entries(screens).forEach(([key, element]) => {
        const isActive = key === name;
        element.classList.toggle("active", isActive);
        element.setAttribute("aria-hidden", isActive ? "false" : "true");
    });
}

function shortText(text, maxLength = 68) {
    const compact = (text || "").replace(/\s+/g, " ").trim();
    if (!compact) {
        return "";
    }
    if (compact.length <= maxLength) {
        return compact;
    }
    return `${compact.slice(0, maxLength - 1)}…`;
}

function createTurnMeta(kind = "turn") {
    const randomPart = Math.random().toString(36).slice(2, 8);
    return {
        turnId: `${kind}-${Date.now().toString(36)}-${randomPart}`,
        turnStartedAtMs: Date.now(),
    };
}

function setHomeSubtitle(text, maxLength = 88) {
    const nextText = shortText(text || defaultIdlePrompt, maxLength) || defaultIdlePrompt;
    faceTranscript.textContent = nextText;
}

function setFaceState(state, transcriptText = null) {
    faceRenderer.setState(state);
    stateLabel.textContent = state.charAt(0).toUpperCase() + state.slice(1);
    if (transcriptText !== null) {
        setHomeSubtitle(transcriptText, state === "speaking" ? 108 : 88);
    }
}

function setStatus(status, detail = "") {
    statusPill.className = `status-pill ${status}`;
    if (detail) {
        statusText.textContent = detail;
        return;
    }
    if (status === "online") {
        statusText.textContent = "Ready";
    } else if (status === "offline") {
        statusText.textContent = "Offline";
    } else if (status === "checking") {
        statusText.textContent = "Checking";
    } else {
        statusText.textContent = "Issue";
    }
}

function updateSpeakingControl() {
    stopSpeakingButton.hidden = !(currentAudio || queuedAudioSegments.length || activeVoiceStreamController);
}

function appendMessage(role, content) {
    const message = document.createElement("div");
    message.className = `message ${role}-message`;
    const label = document.createElement("div");
    label.className = "message-role";
    label.textContent = role === "user" ? "You" : role === "assistant" ? assistantName : "System";
    const text = document.createElement("p");
    text.textContent = content;
    message.append(label, text);
    chatHistory.appendChild(message);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    return { root: message, text };
}

function updateMessageText(messageRef, content) {
    if (!messageRef?.text) {
        return;
    }
    messageRef.text.textContent = content;
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function resetChatView(systemText = "Touchscreen Alfred is ready. Type a message or tap the mic to talk.") {
    chatHistory.innerHTML = "";
    appendMessage("system", systemText);
}

function formatClockTime(timestampSeconds) {
    if (!timestampSeconds) {
        return "";
    }
    try {
        return new Date(timestampSeconds * 1000).toLocaleTimeString([], {
            hour: "numeric",
            minute: "2-digit",
        });
    } catch {
        return "";
    }
}

function formatUptime(totalSeconds) {
    const seconds = Math.max(0, Number(totalSeconds) || 0);
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }
    if (minutes > 0) {
        return `${minutes}m`;
    }
    return `${seconds}s`;
}

function rememberIssue(message) {
    uiLastIssue = message;
    updateDiagnosticsPanel();
}

function updateDiagnosticsPanel() {
    const health = lastServerHealth;
    settingsModel.textContent = health?.llm_model || "Unavailable";

    if (health) {
        healthUpdated.textContent = `Updated ${formatClockTime(Date.now() / 1000)}`;
        healthBackend.textContent = `${health.backend_status === "restarting" ? "Restarting" : "Online"} · ${formatUptime(health.uptime_seconds)}`;
        healthModel.textContent = `${health.llm_model} · ${health.llm_status}`;
        healthStt.textContent = health.stt_ready ? "Ready" : "Missing";
        healthTts.textContent = health.tts_ready ? "Ready" : "Missing";
    } else {
        healthUpdated.textContent = "Waiting for health";
        healthBackend.textContent = "Unavailable";
        healthModel.textContent = "Unavailable";
        healthStt.textContent = "Unknown";
        healthTts.textContent = "Unknown";
    }

    healthMic.textContent = micDiagnosticStatus === "Not tested"
        ? micPermissionStatus
        : `${micPermissionStatus} · ${micDiagnosticStatus}`;
    healthSpeaker.textContent = speakerDiagnosticStatus;

    const backendIssue = health?.last_error
        ? `${health.last_error}${health.last_error_at ? ` · ${formatClockTime(health.last_error_at)}` : ""}`
        : (health?.llm_error || "");
    healthLastError.textContent = uiLastIssue || backendIssue || "No recent errors.";
}

function autoResizeInput() {
    userInput.style.height = "0px";
    userInput.style.height = `${Math.min(userInput.scrollHeight, 220)}px`;
}

async function loadBootstrap() {
    try {
        const response = await fetch("/api/bootstrap");
        const data = await response.json();
        const turns = data.recent_turns || [];
        if (turns.length) {
            chatHistory.innerHTML = "";
            turns.forEach((turn) => appendMessage(turn.role === "assistant" ? "assistant" : "user", turn.content));
            const lastAssistant = [...turns].reverse().find((turn) => turn.role === "assistant");
            if (lastAssistant) {
                setHomeSubtitle(lastAssistant.content);
            }
        }
    } catch (error) {
        console.error("Bootstrap failed:", error);
    }
}

async function refreshHealth() {
    try {
        const response = await fetch("/api/health");
        const data = await response.json();
        lastServerHealth = data;
        if (data.llm_status === "online") {
            setStatus("online", "Ready");
        } else if (data.llm_status === "offline") {
            setStatus("offline", "Offline");
        } else {
            setStatus("error", "Model issue");
        }
        updateDiagnosticsPanel();
    } catch (error) {
        lastServerHealth = null;
        setStatus("offline", "Offline");
        updateDiagnosticsPanel();
    }
}

async function sendChatMessage(message, source = "text", turnMeta = null) {
    const trimmed = message.trim();
    if (!trimmed) {
        return;
    }
    const effectiveTurnMeta = turnMeta || createTurnMeta(source === "voice" ? "voice" : "text");

    appendMessage("user", trimmed);
    setFaceState("thinking", "Thinking...");
    sendButton.disabled = true;
    micButton.disabled = true;

    try {
        if (source === "voice" && voiceToggle.checked) {
            await sendStreamingVoiceMessage(trimmed, effectiveTurnMeta);
            return;
        }
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: trimmed,
                response_mode: source === "voice" ? "voice" : "text",
                synthesize_audio: voiceToggle.checked,
                turn_id: effectiveTurnMeta.turnId,
                turn_started_at_ms: effectiveTurnMeta.turnStartedAtMs,
            }),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Chat request failed.");
        }
        if (data.timings) {
            console.log("[alfred timings][chat]", data.turn_id || effectiveTurnMeta.turnId, data.timings);
        }

        appendMessage("assistant", data.response);
        setHomeSubtitle(data.response, 108);

        if (data.audio_url && voiceToggle.checked) {
            await playResponseAudio(data.audio_url, data.response);
        } else {
            setFaceState("idle", data.response);
        }
    } catch (error) {
        console.error("Chat error:", error);
        rememberIssue(error.message || "Chat request failed.");
        appendMessage("system", error.message || "Alfred could not answer just now.");
        setFaceState("error", "I hit a snag. Please try again.");
    } finally {
        sendButton.disabled = false;
        micButton.disabled = false;
    }
}

async function sendStreamingVoiceMessage(message, turnMeta) {
    const assistantMessage = appendMessage("assistant", "...");
    let latestText = "";
    let finalPayload = null;

    stopVoiceOutput();
    const controller = new AbortController();
    activeVoiceStreamController = controller;
    updateSpeakingControl();

    try {
        const response = await fetch("/api/chat/stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message,
                response_mode: "voice",
                synthesize_audio: true,
                turn_id: turnMeta.turnId,
                turn_started_at_ms: turnMeta.turnStartedAtMs,
            }),
            signal: controller.signal,
        });

        if (!response.ok) {
            const fallback = await response.text();
            throw new Error(fallback || "Streaming chat request failed.");
        }
        if (!response.body) {
            throw new Error("Streaming response body was unavailable.");
        }

        await consumeNdjsonStream(response.body, (event) => {
            if (!event || !event.type) {
                return;
            }

            if (event.type === "partial") {
                latestText = event.text || latestText;
                updateMessageText(assistantMessage, latestText || "…");
                if (latestText) {
                    setHomeSubtitle(latestText, 108);
                }
                return;
            }

            if (event.type === "sentence") {
                latestText = event.full_text || latestText;
                if (event.audio_url) {
                    enqueueAudioSegment(event.audio_url, latestText || event.text || defaultIdlePrompt);
                }
                return;
            }

            if (event.type === "done") {
                finalPayload = event;
                latestText = event.response || latestText;
                updateMessageText(assistantMessage, latestText || "...");
                setHomeSubtitle(latestText || defaultIdlePrompt, 108);
                if (event.timings) {
                    console.log("[alfred timings][chat-stream]", event.turn_id || turnMeta.turnId, event.timings);
                }
                return;
            }

            if (event.type === "error") {
                throw new Error(event.message || "Streaming chat failed.");
            }
        });

        if (!finalPayload) {
            throw new Error("Streaming reply ended before Alfred finished the response.");
        }

        activeVoiceStreamController = null;
        updateSpeakingControl();
        await waitForAudioQueueDrain();
        if (!currentAudio && !queuedAudioSegments.length) {
            setFaceState("idle", latestText || defaultIdlePrompt);
        }
    } catch (error) {
        if (error?.name === "AbortError") {
            updateMessageText(assistantMessage, latestText || "Voice reply stopped.");
            return;
        }
        throw error;
    } finally {
        activeVoiceStreamController = null;
        updateSpeakingControl();
    }
}

async function consumeNdjsonStream(bodyStream, onEvent) {
    const reader = bodyStream.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
        const { done, value } = await reader.read();
        if (done) {
            break;
        }
        buffer += decoder.decode(value, { stream: true });
        while (true) {
            const newlineIndex = buffer.indexOf("\n");
            if (newlineIndex === -1) {
                break;
            }
            const line = buffer.slice(0, newlineIndex).trim();
            buffer = buffer.slice(newlineIndex + 1);
            if (!line) {
                continue;
            }
            onEvent(JSON.parse(line));
        }
    }

    buffer += decoder.decode();
    const tail = buffer.trim();
    if (tail) {
        onEvent(JSON.parse(tail));
    }
}

async function playResponseAudio(audioUrl, transcriptText) {
    stopVoiceOutput();
    enqueueAudioSegment(audioUrl, transcriptText);
    await waitForAudioQueueDrain();
}

function teardownCurrentAudioElement() {
    if (currentAudio) {
        currentAudio.pause();
        currentAudio.currentTime = 0;
        currentAudio = null;
    }
    faceRenderer.mouthOpen = 0;
    currentAnalyser = null;
    currentDataArray = null;
}

function resolveAudioQueueDrain() {
    if (currentAudio || queuedAudioSegments.length) {
        return;
    }
    const resolvers = audioQueueDrainResolvers.splice(0);
    resolvers.forEach((resolve) => resolve());
}

function waitForAudioQueueDrain() {
    if (!currentAudio && !queuedAudioSegments.length) {
        return Promise.resolve();
    }
    return new Promise((resolve) => {
        audioQueueDrainResolvers.push(resolve);
    });
}

function enqueueAudioSegment(audioUrl, transcriptText) {
    if (!audioUrl) {
        return;
    }
    queuedAudioSegments.push({ audioUrl, transcriptText });
    updateSpeakingControl();
    void playNextAudioSegment();
}

async function playNextAudioSegment() {
    if (currentAudio || !queuedAudioSegments.length) {
        updateSpeakingControl();
        return;
    }

    const segment = queuedAudioSegments.shift();
    if (!segment) {
        resolveAudioQueueDrain();
        updateSpeakingControl();
        return;
    }

    setFaceState("speaking", segment.transcriptText || faceTranscript.textContent || defaultIdlePrompt);
    speakerDiagnosticStatus = "Playing audio";
    updateDiagnosticsPanel();

    currentAudio = new Audio(segment.audioUrl);
    currentAudio.preload = "auto";
    updateSpeakingControl();
    setupAudioVisualizer(currentAudio);

    currentAudio.onended = () => {
        teardownCurrentAudioElement();
        if (queuedAudioSegments.length) {
            void playNextAudioSegment();
            return;
        }
        speakerDiagnosticStatus = "Working";
        updateDiagnosticsPanel();
        if (!activeVoiceStreamController) {
            setFaceState("idle", segment.transcriptText || defaultIdlePrompt);
        }
        resolveAudioQueueDrain();
        updateSpeakingControl();
    };

    currentAudio.onerror = () => {
        teardownCurrentAudioElement();
        speakerDiagnosticStatus = "Playback failed";
        rememberIssue("Speaker playback failed.");
        updateDiagnosticsPanel();
        if (queuedAudioSegments.length) {
            void playNextAudioSegment();
            return;
        }
        if (!activeVoiceStreamController) {
            setFaceState("idle", segment.transcriptText || defaultIdlePrompt);
        }
        resolveAudioQueueDrain();
        updateSpeakingControl();
    };

    try {
        if (currentAudioContext && currentAudioContext.state === "suspended") {
            await currentAudioContext.resume();
        }
        await currentAudio.play();
    } catch (error) {
        console.error("Audio playback failed:", error);
        teardownCurrentAudioElement();
        speakerDiagnosticStatus = "Playback failed";
        rememberIssue("Speaker playback failed.");
        updateDiagnosticsPanel();
        if (queuedAudioSegments.length) {
            void playNextAudioSegment();
            return;
        }
        if (!activeVoiceStreamController) {
            setFaceState("idle", segment.transcriptText || defaultIdlePrompt);
        }
        resolveAudioQueueDrain();
        updateSpeakingControl();
    }
}

function stopVoiceOutput() {
    if (activeVoiceStreamController) {
        activeVoiceStreamController.abort();
        activeVoiceStreamController = null;
    }
    queuedAudioSegments = [];
    teardownCurrentAudioElement();
    resolveAudioQueueDrain();
    updateSpeakingControl();
}

function setupAudioVisualizer(audioElement) {
    if (audioElement._alfredVizReady) {
        return;
    }
    audioElement._alfredVizReady = true;

    if (!currentAudioContext) {
        currentAudioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    const source = currentAudioContext.createMediaElementSource(audioElement);
    currentAnalyser = currentAudioContext.createAnalyser();
    currentAnalyser.fftSize = 256;
    currentDataArray = new Uint8Array(currentAnalyser.frequencyBinCount);
    source.connect(currentAnalyser);
    currentAnalyser.connect(currentAudioContext.destination);

    const sync = () => {
        if (!currentAudio || currentAudio.paused || !currentAnalyser || !currentDataArray) {
            faceRenderer.mouthOpen = 0;
            return;
        }
        currentAnalyser.getByteTimeDomainData(currentDataArray);
        let sum = 0;
        for (let index = 0; index < currentDataArray.length; index += 1) {
            sum += Math.abs(currentDataArray[index] - 128);
        }
        faceRenderer.mouthOpen = (sum / currentDataArray.length) * 4.6;
        requestAnimationFrame(sync);
    };
    sync();
}

function clearRecordingTimer() {
    if (recordingAutoStopTimer) {
        window.clearTimeout(recordingAutoStopTimer);
        recordingAutoStopTimer = null;
    }
}

async function startRecording(mode = "chat") {
    if (isRecording) {
        stopRecording();
        return;
    }

    stopVoiceOutput();

    try {
        if (mode !== "mic-test") {
            currentTurnMeta = createTurnMeta("voice");
        }
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        currentRecordingMode = mode;
        isRecording = true;
        micButton.classList.add("recording");
        micPermissionStatus = "Permission granted";
        micDiagnosticStatus = mode === "mic-test" ? "Listening for test" : micDiagnosticStatus;
        updateDiagnosticsPanel();
        setFaceState("listening", mode === "mic-test" ? "Microphone test: speak now." : "Listening...");

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };

        mediaRecorder.onstop = async () => {
            stream.getTracks().forEach((track) => track.stop());
            clearRecordingTimer();
            micButton.classList.remove("recording");
            isRecording = false;
            const finishedMode = currentRecordingMode;
            currentRecordingMode = "chat";
            setFaceState("thinking", finishedMode === "mic-test" ? "Checking microphone..." : "Transcribing...");
            await transcribeRecording(finishedMode);
        };

        mediaRecorder.start();
        if (mode === "mic-test") {
            recordingAutoStopTimer = window.setTimeout(() => {
                if (isRecording) {
                    stopRecording();
                }
            }, 4000);
        }
    } catch (error) {
        console.error("Microphone access failed:", error);
        micPermissionStatus = "Permission blocked";
        micDiagnosticStatus = "Unavailable";
        rememberIssue("Microphone access failed.");
        updateDiagnosticsPanel();
        appendMessage("system", "Microphone access failed. Please allow mic permissions for Alfred.");
        setFaceState("error", "Microphone access failed.");
    }
}

function stopRecording() {
    if (mediaRecorder && isRecording) {
        mediaRecorder.stop();
    }
}

async function transcribeRecording(mode = "chat") {
    if (!audioChunks.length) {
        if (mode === "mic-test") {
            micDiagnosticStatus = "No audio detected";
            rememberIssue("Microphone test did not capture any audio.");
            updateDiagnosticsPanel();
        }
        currentTurnMeta = null;
        setFaceState("idle", "I did not hear enough audio.");
        return;
    }

    const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
    const formData = new FormData();
    formData.append("audio", audioBlob, "alfred-touch.webm");
    if (currentTurnMeta) {
        formData.append("turn_id", currentTurnMeta.turnId);
        formData.append("turn_started_at_ms", String(currentTurnMeta.turnStartedAtMs));
    }

    try {
        const response = await fetch("/api/transcribe", {
            method: "POST",
            body: formData,
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Transcription failed.");
        }
        if (data.timings) {
            console.log("[alfred timings][stt]", data.turn_id || currentTurnMeta?.turnId, data.timings);
        }
        if (!data.text) {
            if (mode === "mic-test") {
                micDiagnosticStatus = "No speech detected";
                rememberIssue("Microphone test did not detect speech.");
                updateDiagnosticsPanel();
            }
            currentTurnMeta = null;
            setFaceState("idle", "I did not catch that.");
            return;
        }
        if (mode === "mic-test") {
            micDiagnosticStatus = `Working · "${shortText(data.text, 32)}"`;
            updateDiagnosticsPanel();
            appendMessage("system", `Microphone test heard: ${data.text}`);
            currentTurnMeta = null;
            setFaceState("idle", "Microphone test complete.");
            return;
        }
        const voiceTurnMeta = currentTurnMeta || (data.turn_id ? { turnId: data.turn_id, turnStartedAtMs: Date.now() } : null);
        await sendChatMessage(data.text, "voice", voiceTurnMeta);
    } catch (error) {
        console.error("Transcription error:", error);
        if (mode === "mic-test") {
            micDiagnosticStatus = "Test failed";
        }
        rememberIssue(error.message || "Transcription failed.");
        updateDiagnosticsPanel();
        appendMessage("system", error.message || "Transcription failed.");
        setFaceState("error", "Transcription failed.");
    } finally {
        audioChunks = [];
        currentTurnMeta = null;
    }
}

async function refreshMicrophonePermission() {
    if (!navigator.mediaDevices?.getUserMedia) {
        micPermissionStatus = "Browser mic unavailable";
        updateDiagnosticsPanel();
        return;
    }
    if (!navigator.permissions?.query) {
        micPermissionStatus = "Permission unknown";
        updateDiagnosticsPanel();
        return;
    }

    try {
        const permission = await navigator.permissions.query({ name: "microphone" });
        const applyState = () => {
            if (permission.state === "granted") {
                micPermissionStatus = "Permission granted";
            } else if (permission.state === "denied") {
                micPermissionStatus = "Permission blocked";
            } else {
                micPermissionStatus = "Permission needed";
            }
            updateDiagnosticsPanel();
        };
        applyState();
        permission.onchange = applyState;
    } catch (error) {
        micPermissionStatus = "Permission unknown";
        updateDiagnosticsPanel();
    }
}

async function waitForBackendReady(maxAttempts = 30, intervalMs = 800) {
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
        try {
            const response = await fetch(`/api/health?ts=${Date.now()}`, { cache: "no-store" });
            if (response.ok) {
                const data = await response.json();
                lastServerHealth = data;
                updateDiagnosticsPanel();
                return data;
            }
        } catch (error) {
            // Keep waiting through restart downtime.
        }
        await new Promise((resolve) => window.setTimeout(resolve, intervalMs));
    }
    throw new Error("Backend restart timed out.");
}

composer.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = userInput.value;
    if (!message.trim()) {
        return;
    }
    userInput.value = "";
    autoResizeInput();
    await sendChatMessage(message, "text");
});

chatOpenButton.addEventListener("click", () => showScreen("chat"));
chatBackButton.addEventListener("click", () => showScreen("home"));
settingsOpenButton.addEventListener("click", () => showScreen("settings"));
settingsBackButton.addEventListener("click", () => showScreen("home"));
openHealthButton.addEventListener("click", () => showScreen("health"));
healthBackButton.addEventListener("click", () => showScreen("settings"));

micButton.addEventListener("click", () => {
    showScreen("home");
    startRecording();
});

stopSpeakingButton.addEventListener("click", () => {
    if (!currentAudio && !queuedAudioSegments.length && !activeVoiceStreamController) {
        return;
    }
    stopVoiceOutput();
    speakerDiagnosticStatus = "Stopped by user";
    updateDiagnosticsPanel();
    setFaceState("idle", faceTranscript.textContent || defaultIdlePrompt);
});

userInput.addEventListener("input", autoResizeInput);
userInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        composer.requestSubmit();
    }
});

clearScreenButton.addEventListener("click", () => {
    resetChatView("Conversation view cleared. Alfred still remembers the recent chat unless you reset memory.");
});

resetMemoryButton.addEventListener("click", async () => {
    const confirmed = window.confirm("Reset Alfred's recent conversation memory and start fresh?");
    if (!confirmed) {
        return;
    }

    resetMemoryButton.disabled = true;
    try {
        const response = await fetch("/api/memory/reset", { method: "POST" });
        const data = await response.json();
        if (!response.ok || !data.ok) {
            throw new Error(data.detail || "Memory reset failed.");
        }

        stopVoiceOutput();
        resetChatView("Conversation memory cleared. Alfred has forgotten the recent chat.");
        showScreen("home");
        setFaceState("idle", defaultIdlePrompt);
        userInput.value = "";
        autoResizeInput();
    } catch (error) {
        console.error("Memory reset failed:", error);
        rememberIssue(error.message || "Memory reset failed.");
        appendMessage("system", error.message || "Memory reset failed.");
        setFaceState("error", "Memory reset failed.");
    } finally {
        resetMemoryButton.disabled = false;
    }
});

testSpeakerButton.addEventListener("click", async () => {
    testSpeakerButton.disabled = true;
    try {
        const response = await fetch("/api/diagnostics/speaker-test", { method: "POST" });
        const data = await response.json();
        if (!response.ok || !data.ok) {
            throw new Error(data.detail || "Speaker test failed.");
        }

        speakerDiagnosticStatus = "Playing test";
        updateDiagnosticsPanel();
        showScreen("home");
        await playResponseAudio(data.audio_url, data.text);
    } catch (error) {
        console.error("Speaker test failed:", error);
        speakerDiagnosticStatus = "Test failed";
        rememberIssue(error.message || "Speaker test failed.");
        updateDiagnosticsPanel();
        appendMessage("system", error.message || "Speaker test failed.");
        setFaceState("error", "Speaker test failed.");
    } finally {
        testSpeakerButton.disabled = false;
    }
});

testMicrophoneButton.addEventListener("click", async () => {
    if (isRecording) {
        return;
    }
    showScreen("home");
    await startRecording("mic-test");
});

restartBackendButton.addEventListener("click", async () => {
    const confirmed = window.confirm("Restart Alfred's backend now?");
    if (!confirmed) {
        return;
    }

    restartBackendButton.disabled = true;
    stopVoiceOutput();
    speakerDiagnosticStatus = "Ready to test";
    try {
        const response = await fetch("/api/diagnostics/restart", { method: "POST" });
        const data = await response.json();
        if (!response.ok || !data.ok) {
            throw new Error(data.detail || "Backend restart failed.");
        }

        showScreen("home");
        setStatus("checking", "Restarting");
        setFaceState("thinking", "Restarting Alfred...");
        await new Promise((resolve) => window.setTimeout(resolve, 900));
        await waitForBackendReady();
        window.location.reload();
    } catch (error) {
        console.error("Backend restart failed:", error);
        rememberIssue(error.message || "Backend restart failed.");
        appendMessage("system", error.message || "Backend restart failed.");
        setFaceState("error", "Backend restart failed.");
        await refreshHealth();
    } finally {
        restartBackendButton.disabled = false;
    }
});

autoResizeInput();
showScreen(activeScreen);
setFaceState("idle", defaultIdlePrompt);
updateSpeakingControl();
updateDiagnosticsPanel();
refreshMicrophonePermission();
loadBootstrap();
refreshHealth();
setInterval(refreshHealth, 20000);
