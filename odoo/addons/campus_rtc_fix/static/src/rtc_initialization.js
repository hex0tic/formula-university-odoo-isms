/** @odoo-module **/

import { PeerToPeer, STREAM_TYPE } from "@mail/discuss/call/common/peer_to_peer";
import { patch } from "@web/core/utils/patch";

// Match the audio/camera/screen ordering used by Peer.getTransceiver().
const MEDIA_SLOTS = [STREAM_TYPE.AUDIO, STREAM_TYPE.CAMERA, STREAM_TYPE.SCREEN];

patch(PeerToPeer.prototype, {
    // Temporary metadata-only diagnostics for the unresolved LAN call issue.
    // Do not log SDP, ICE addresses, TURN credentials, or media content.
    async handleNotification(id, content) {
        this.setLoggingLevel("debug");
        const message = JSON.parse(content);
        this._emitLog(id, `rtc-diag-v2 receive ${message.event}; channel=${message.channelId}; localChannel=${this.channelId}; self=${this.selfId}`, "debug");
        return super.handleNotification(id, content);
    },
    async _busNotify(event, options = {}) {
        this.setLoggingLevel("debug");
        for (const id of options.targets || this.peers.keys()) {
            this._emitLog(id, `rtc-diag-v2 send ${event}; self=${this.selfId}`, "debug");
        }
        return super._busNotify(event, options);
    },
    _createPeer(id, options = {}) {
        this.setLoggingLevel("debug");
        const peer = super._createPeer(id, options);
        const connection = peer.connection;
        for (const event of ["signalingstatechange", "negotiationneeded"]) {
            connection.addEventListener(event, () => {
                this._emitLog(id, `rtc-diag-v2 ${event}; signaling=${connection.signalingState}; local=${connection.localDescription?.type || "none"}; remote=${connection.remoteDescription?.type || "none"}`, "debug");
            });
        }
        if (!this._isStreamingEnabled || !peer.connection) {
            return peer;
        }
        // Run synchronously before negotiationneeded or a view's updateDownload.
        // A data-only initial offer otherwise leaves no media transceivers for
        // updateDownload, causing recovery before media negotiation completes.
        if (peer.connection.getTransceivers().length === 0) {
            for (const streamType of MEDIA_SLOTS) {
                const track = this._tracks[streamType];
                peer.connection.addTransceiver(
                    track || (streamType === STREAM_TYPE.AUDIO ? "audio" : "video"),
                    { direction: peer.getRecommendedTransceiverDirection(streamType, Boolean(track)) }
                );
            }
        }
        return peer;
    },
});
