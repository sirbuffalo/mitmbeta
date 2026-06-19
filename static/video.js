(function () {
    const video = document.getElementById('lesson-video');
    const fullscreenShell = document.getElementById('video-fullscreen-shell');
    const videoFrame = video.closest('.video-frame');
    const title = document.getElementById('video-title');
    const titleBars = document.getElementById('video-title-bars');
    const controls = document.getElementById('video-controls');
    const playToggle = document.getElementById('video-play-toggle');
    const scrubber = document.getElementById('video-scrubber');
    const interjectionMarkers = document.getElementById('video-interjection-markers');
    const videoProgress = document.getElementById('video-progress');
    const videoPlayhead = document.getElementById('video-playhead');
    const pauseOverlay = document.getElementById('video-pause-overlay');
    const pauseContent = document.getElementById('video-pause-content');
    const pauseContinue = document.getElementById('video-pause-continue');
    const currentTime = document.getElementById('video-current-time');
    const duration = document.getElementById('video-duration');
    const volumeControl = document.getElementById('video-volume-control');
    const volumeToggle = document.getElementById('video-volume-toggle');
    const volume = document.getElementById('video-volume');
    const settingsControl = document.getElementById('video-settings-control');
    const settingsToggle = document.getElementById('video-settings-toggle');
    const qualitySelect = document.getElementById('video-quality');
    const speedSelect = document.getElementById('video-speed');
    const customSpeedControl = document.getElementById('video-custom-speed-control');
    const customSpeed = document.getElementById('video-custom-speed');
    const customSpeedLabel = document.getElementById('video-custom-speed-label');
    const fullscreenToggle = document.getElementById('video-fullscreen-toggle');
    const skipInterjection = document.getElementById('skip-interjection');

    if (!video || !fullscreenShell || !videoFrame || !title || !titleBars || !controls || !playToggle || !scrubber || !interjectionMarkers || !videoProgress || !videoPlayhead || !pauseOverlay || !pauseContent || !pauseContinue || !currentTime || !duration || !volumeControl || !volumeToggle || !volume || !settingsControl || !settingsToggle || !qualitySelect || !speedSelect || !customSpeedControl || !customSpeed || !customSpeedLabel || !fullscreenToggle || !skipInterjection) {
        return;
    }

    const mainTitle = video.dataset.mainTitle;
    const progressUrl = video.dataset.progressUrl;
    const savedStartTime = Math.max(Number(video.dataset.startTime || 0), 0);
    const finishedVideos = new Set(JSON.parse(video.dataset.finishedVideos || '[]'));
    const ranges = JSON.parse(video.dataset.interjections || '[]')
        .filter((range) => Number.isFinite(range.start) && Number.isFinite(range.end) && range.end > range.start)
        .sort((left, right) => left.start - right.start);
    const pauses = JSON.parse(video.dataset.pauses || '[]')
        .filter((pause) => Number.isFinite(pause.time) && typeof pause.markdown === 'string')
        .sort((left, right) => left.time - right.time)
        .map((pause, index) => ({
            ...pause,
            id: pause.id ?? `pause-${index}-${pause.time}`,
        }));
    const qualitySources = JSON.parse(video.dataset.qualitySources || '[]');
    const maxMarkerDepth = Math.min(Math.max(...ranges.map((range) => range.depth || 0), 0), 6);
    const timelineColors = ['#8edda2', '#ff1f1f', '#ff9f1f', '#ffd21f', '#2bcf4f', '#2f80ff', '#8b5cff'];
    const titleBarColors = ['#c8f2d2', '#f7c7c7', '#f4d7b4', '#f4e8ad', '#c8f2d2', '#c8dcf7', '#d8ccf7'];
    const titleBarHeight = 46;
    const reservedTitleBarsHeight = Math.max(maxMarkerDepth, 1) * titleBarHeight;
    const progressSaveIntervalMs = 5000;
    let timelineAnimationFrame;
    let controlsHideTimer;
    let hlsPlayer = null;
    let lastRequestedSeekTime = null;
    let markerDuration = null;
    let lastProgressSaveTime = 0;
    let lastSavedVideoSecond = savedStartTime;
    let lastPlaybackTime = savedStartTime;
    let selectedPresetSpeed = 1;
    let titleStackKey = '';
    const dismissedPauses = new Set(pauses.filter((pause) => pause.time < savedStartTime - 0.5).map((pause) => pause.id));
    let scrubbing = false;

    const iconPaths = {
        fullscreen: 'M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z',
        fullscreen_exit: 'M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z',
        pause: 'M6 19h4V5H6v14zm8-14v14h4V5h-4z',
        play_arrow: 'M8 5v14l11-7z',
        settings: 'M19.43 12.98c.04-.32.07-.65.07-.98s-.02-.66-.07-.98l2.11-1.65c.19-.15.24-.42.12-.64l-2-3.46c-.12-.22-.37-.31-.6-.22l-2.49 1c-.52-.4-1.08-.73-1.69-.98L14.5 2.42C14.47 2.18 14.25 2 14 2h-4c-.25 0-.46.18-.5.42L9.12 5.07c-.61.25-1.18.59-1.69.98l-2.49-1c-.23-.08-.48 0-.6.22l-2 3.46c-.13.22-.07.49.12.64l2.11 1.65c-.04.32-.08.65-.08.98s.03.66.08.98l-2.11 1.65c-.19.15-.24.42-.12.64l2 3.46c.12.22.37.31.6.22l2.49-1c.52.4 1.08.73 1.69.98l.38 2.65c.04.24.25.42.5.42h4c.25 0 .47-.18.5-.42l.38-2.65c.61-.25 1.18-.59 1.69-.98l2.49 1c.23.08.48 0 .6-.22l2-3.46c.12-.22.07-.49-.12-.64l-2.11-1.65zM12 15.5A3.5 3.5 0 1 1 12 8a3.5 3.5 0 0 1 0 7.5z',
        volume_down: 'M18.5 12c0-1.77-1-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM5 9v6h4l5 5V4L9 9H5z',
        volume_off: 'M16.5 12c0-1.77-1-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zM19 12c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.62 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73L16.25 17.52c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z',
        volume_up: 'M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z',
    };

    function iconSvg(name) {
        const path = iconPaths[name] || iconPaths.settings;
        return `<svg class="video-control-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="${path}"></path></svg>`;
    }

    function renderInitialIcons() {
        document.querySelectorAll('.video-control-icon[data-icon]').forEach((icon) => {
            icon.outerHTML = iconSvg(icon.dataset.icon);
        });
    }

    function formatTime(seconds) {
        if (!Number.isFinite(seconds)) {
            return '0:00';
        }

        const roundedSeconds = Math.floor(seconds);
        const minutes = Math.floor(roundedSeconds / 60);
        const remainingSeconds = String(roundedSeconds % 60).padStart(2, '0');
        return `${minutes}:${remainingSeconds}`;
    }

    function getVideoDuration() {
        return Number.isFinite(video.duration) && video.duration > 0 ? video.duration : 0;
    }

    function getCurrentRange() {
        const time = video.currentTime || 0;
        return ranges
            .filter((range) => time >= range.start && time < range.end)
            .sort((left, right) => right.depth - left.depth || right.start - left.start)[0] || null;
    }

    function getCurrentRanges() {
        const time = video.currentTime || 0;
        return ranges
            .filter((range) => time >= range.start && time < range.end)
            .sort((left, right) => left.depth - right.depth || left.start - right.start);
    }

    function getCurrentInterjectionRange() {
        const time = video.currentTime || 0;
        return ranges
            .filter((range) => range.depth > 0 && time >= range.start && time < range.end)
            .sort((left, right) => right.depth - left.depth)[0] || null;
    }

    function updatePlayToggle() {
        playToggle.innerHTML = video.paused
            ? iconSvg('play_arrow')
            : iconSvg('pause');
        playToggle.setAttribute('aria-label', video.paused ? 'Play' : 'Pause');
    }

    function updateVolumeIcon() {
        let icon = 'volume_up';
        if (video.muted || video.volume === 0) {
            icon = 'volume_off';
        } else if (video.volume < 0.5) {
            icon = 'volume_down';
        }

        volumeToggle.innerHTML = iconSvg(icon);
    }

    function updateFullscreenToggle() {
        const isFullscreen = document.fullscreenElement === fullscreenShell;
        fullscreenToggle.innerHTML = iconSvg(isFullscreen ? 'fullscreen_exit' : 'fullscreen');
        fullscreenToggle.setAttribute('aria-label', isFullscreen ? 'Exit fullscreen' : 'Fullscreen');
    }

    function updateTitleAndSkip() {
        const activeRanges = getCurrentRanges();
        const range = activeRanges[activeRanges.length - 1] || null;
        const interjectionRange = getCurrentInterjectionRange();
        const displayRanges = [];
        activeRanges.forEach((activeRange) => {
            const key = `${activeRange.depth}:${activeRange.video_id || activeRange.title}`;
            const existingIndex = displayRanges.findIndex((displayRange) => `${displayRange.depth}:${displayRange.video_id || displayRange.title}` === key);
            if (existingIndex === -1) {
                displayRanges.push(activeRange);
            } else if (activeRange.is_container && !displayRanges[existingIndex].is_container) {
                displayRanges[existingIndex] = activeRange;
            }
        });
        if (displayRanges.length === 0) {
            displayRanges.push({ depth: 0, title: mainTitle });
        }
        title.textContent = range ? range.title : mainTitle;
        const nextTitleStackKey = JSON.stringify(displayRanges.map((activeRange) => [
            activeRange.depth,
            activeRange.video_id || '',
            activeRange.title || '',
            activeRange.skip_end ?? '',
            finishedVideos.has(activeRange.video_id),
        ]));
        if (nextTitleStackKey !== titleStackKey) {
            titleStackKey = nextTitleStackKey;
            titleBars.replaceChildren();
            [...displayRanges].reverse().forEach((activeRange) => {
                const activeDepth = Math.min(Math.max(activeRange.depth, 0), 6);
                const bar = document.createElement('div');
                const spacer = document.createElement('div');
                const heading = document.createElement('h1');
                bar.className = 'video-title-bar';
                bar.style.setProperty('--active-title-bar-color', titleBarColors[activeDepth]);
                bar.style.setProperty('--active-skip-color', timelineColors[activeDepth]);
                heading.textContent = activeRange.title || mainTitle;
                bar.append(spacer, heading);
                if (activeRange.depth > 0 && Number.isFinite(activeRange.skip_end)) {
                    const skipButton = document.createElement('button');
                    skipButton.className = 'skip-interjection';
                    skipButton.type = 'button';
                    skipButton.textContent = 'Skip';
                    skipButton.dataset.skipEnd = String(activeRange.skip_end);
                    if (finishedVideos.has(activeRange.video_id)) {
                        skipButton.classList.add('is-finished');
                    }
                    bar.append(skipButton);
                } else {
                    bar.append(document.createElement('div'));
                }
                titleBars.append(bar);
            });
            fullscreenShell.style.setProperty('--active-title-bars-height', `${reservedTitleBarsHeight}px`);
        }
        skipInterjection.hidden = !interjectionRange || !Number.isFinite(interjectionRange.skip_end);
        skipInterjection.classList.toggle(
            'is-finished',
            Boolean(interjectionRange && finishedVideos.has(interjectionRange.video_id))
        );
    }

    function renderInterjectionMarkers() {
        const totalDuration = getVideoDuration();
        interjectionMarkers.replaceChildren();
        markerDuration = totalDuration;
        if (totalDuration <= 0) {
            return;
        }

        videoPlayhead.style.setProperty('--timeline-playhead-above', `${4 + ((maxMarkerDepth + 1) * 8)}px`);

        function createMarker(range, depth) {
            const marker = document.createElement('span');
            const startPercent = (range.start / totalDuration) * 100;
            const widthPercent = ((range.end - range.start) / totalDuration) * 100;
            marker.className = 'video-interjection-marker';
            marker.dataset.depth = String(depth);
            marker.title = range.title || 'Interjection';
            marker.style.left = `${Math.max(startPercent, 0)}%`;
            marker.style.width = `${Math.max(widthPercent, 0)}%`;
            return marker;
        }

        ranges.forEach((range) => {
            if (range.depth <= 0) {
                return;
            }

            const markerDepth = Math.min(range.depth, 6);
            for (let depth = 1; depth <= markerDepth; depth += 1) {
                interjectionMarkers.append(createMarker(range, depth));
            }
        });
    }

    function updateTimeline() {
        refreshDismissedPauses();
        const totalDuration = getVideoDuration();
        if (markerDuration !== totalDuration) {
            renderInterjectionMarkers();
        }

        const timelineValue = scrubbing ? Number(scrubber.value) : (video.currentTime || 0);
        const progress = totalDuration > 0 ? (timelineValue / totalDuration) * 100 : 0;

        scrubber.max = String(totalDuration || 100);
        if (!scrubbing) {
            scrubber.value = String(timelineValue);
        }

        const progressWidth = scrubber.clientWidth * (progress / 100);
        videoProgress.style.width = `${Math.max(progressWidth, 0)}px`;
        videoPlayhead.style.left = `${Math.max(progressWidth, 0)}px`;

        currentTime.textContent = formatTime(timelineValue);
        duration.textContent = formatTime(totalDuration);
        updateTitleAndSkip();
    }

    function refreshDismissedPauses() {
        const currentTimeValue = video.currentTime || 0;
        pauses.forEach((pause) => {
            if (Math.abs(currentTimeValue - pause.time) > 0.75) {
                dismissedPauses.delete(pause.id);
            }
        });
    }

    function animateTimeline() {
        updateTimeline();
        if (!video.paused) {
            timelineAnimationFrame = requestAnimationFrame(animateTimeline);
        }
    }

    function startTimelineAnimation() {
        cancelAnimationFrame(timelineAnimationFrame);
        timelineAnimationFrame = requestAnimationFrame(animateTimeline);
    }

    function stopTimelineAnimation() {
        cancelAnimationFrame(timelineAnimationFrame);
        updateTimeline();
    }

    function showControls() {
        if (!pauseOverlay.hidden) {
            return;
        }

        controls.classList.add('is-visible');
        clearTimeout(controlsHideTimer);

        if (!video.paused && !volumeControl.classList.contains('is-open')) {
            controlsHideTimer = setTimeout(() => {
                controls.classList.remove('is-visible');
                settingsControl.classList.remove('is-open');
            }, 1800);
        }
    }

    function updateControlsVisibility() {
        if (!pauseOverlay.hidden) {
            controls.classList.remove('is-visible');
            clearTimeout(controlsHideTimer);
            return;
        }

        if (video.paused) {
            controls.classList.add('is-visible');
            clearTimeout(controlsHideTimer);
        } else {
            showControls();
        }
    }

    function playWhenReady() {
        const playPromise = video.play();
        if (playPromise) {
            playPromise.catch(() => {});
        }
    }

    function escapeHtml(text) {
        return text
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }

    function markdownToHtml(markdown) {
        if (!markdown.trim()) {
            return '';
        }

        return markdown
            .trim()
            .split(/\n{2,}/)
            .map((block) => {
                const text = block.trim();
                const lines = text.split('\n');
                if (text.startsWith('# ')) {
                    return `<h1>${escapeHtml(lines[0].slice(2).trim())}</h1>${markdownToHtml(lines.slice(1).join('\n'))}`;
                }

                if (text.startsWith('## ')) {
                    return `<h2>${escapeHtml(lines[0].slice(3).trim())}</h2>${markdownToHtml(lines.slice(1).join('\n'))}`;
                }

                if (lines.every((line) => line.trim().startsWith('- '))) {
                    const items = lines
                        .map((line) => `<li>${escapeHtml(line.trim().slice(2))}</li>`)
                        .join('');
                    return `<ul>${items}</ul>`;
                }

                return `<p>${escapeHtml(text).replaceAll('\n', '<br>')}</p>`;
            })
            .join('');
    }

    function showPause(pause) {
        pauseContent.innerHTML = markdownToHtml(pause.markdown);
        pauseOverlay.hidden = false;
        controls.classList.remove('is-visible');
        settingsControl.classList.remove('is-open');
        volumeControl.classList.remove('is-open');
        video.pause();
        updateControlsVisibility();
    }

    function showPauseAtCurrentTime() {
        const currentTimeValue = video.currentTime || 0;
        const pause = pauses.find((candidate) => (
            !dismissedPauses.has(candidate.id)
            && Math.abs(currentTimeValue - candidate.time) <= 0.5
        ));
        if (pause) {
            video.currentTime = pause.time;
            lastPlaybackTime = pause.time;
            showPause(pause);
            return true;
        }

        return false;
    }

    function maybeShowPause(previousTime, currentTimeValue) {
        const timeDelta = currentTimeValue - previousTime;
        if (video.seeking || scrubbing || timeDelta <= 0 || timeDelta > 2.5 || !pauseOverlay.hidden) {
            return;
        }

        const pause = pauses.find((candidate) => (
            !dismissedPauses.has(candidate.id)
            && previousTime < candidate.time
            && currentTimeValue >= candidate.time
        ));
        if (pause) {
            video.currentTime = pause.time;
            lastPlaybackTime = pause.time;
            showPause(pause);
        }
    }

    function formatSpeed(rate) {
        if (rate === 0) {
            return '0x';
        }

        return `${Number(rate.toFixed(2))}x`;
    }

    function speedFromSliderValue(value) {
        const sliderValue = Math.max(Math.min(Number(value), 100), 0);
        if (sliderValue === 0) {
            return 0;
        }

        const minRate = 0.05;
        return minRate * ((5 / minRate) ** (sliderValue / 100));
    }

    function sliderValueFromSpeed(rate) {
        const playbackRate = Math.max(Math.min(Number(rate), 5), 0);
        if (playbackRate === 0) {
            return 0;
        }

        const minRate = 0.05;
        return (Math.log(playbackRate / minRate) / Math.log(5 / minRate)) * 100;
    }

    function setPlaybackSpeed(rate) {
        const playbackRate = Math.max(Math.min(Number(rate), 5), 0);
        if (playbackRate === 0) {
            video.pause();
        } else {
            video.playbackRate = playbackRate;
        }
        customSpeedLabel.textContent = formatSpeed(playbackRate);
    }

    function updateCustomSpeed() {
        setPlaybackSpeed(speedFromSliderValue(customSpeed.value));
    }

    function setCustomSpeedFromRate(rate) {
        customSpeed.value = String(sliderValueFromSpeed(rate));
        setPlaybackSpeed(speedFromSliderValue(customSpeed.value));
    }

    function saveProgress(force = false) {
        if (!progressUrl || !Number.isFinite(video.currentTime)) {
            return;
        }

        const now = Date.now();
        const videoSecond = video.currentTime || 0;
        if (!force && (now - lastProgressSaveTime < progressSaveIntervalMs || Math.abs(videoSecond - lastSavedVideoSecond) < 0.5)) {
            return;
        }

        lastProgressSaveTime = now;
        lastSavedVideoSecond = videoSecond;
        fetch(progressUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                seconds: videoSecond,
                duration: getVideoDuration(),
            }),
            keepalive: force,
        }).catch(() => {});
    }

    function getProgressUrl(videoId) {
        return `/video/${encodeURIComponent(videoId)}/progress`;
    }

    function markVideoFinished(videoId) {
        if (!videoId || finishedVideos.has(videoId)) {
            return;
        }

        finishedVideos.add(videoId);
        fetch(getProgressUrl(videoId), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                seconds: 1,
                duration: 1,
                finished: true,
            }),
        }).catch(() => {});
        updateTitleAndSkip();
    }

    function markNaturallyCompletedInterjections() {
        const currentTimeValue = video.currentTime || 0;
        const previousTime = lastPlaybackTime;
        const timeDelta = currentTimeValue - previousTime;
        lastPlaybackTime = currentTimeValue;

        maybeShowPause(previousTime, currentTimeValue);

        if (video.seeking || scrubbing || timeDelta <= 0 || timeDelta > 2.5) {
            return;
        }

        ranges
            .filter((range) => (
                range.depth > 0
                && range.video_id
                && previousTime >= range.start - 0.25
                && previousTime < range.end
                && currentTimeValue >= range.end
            ))
            .forEach((range) => markVideoFinished(range.video_id));
    }

    function seekTo(seconds) {
        const totalDuration = getVideoDuration();
        const targetTime = Math.max(Math.min(seconds, totalDuration), 0);
        pauses.forEach((pause) => {
            if (Math.abs(targetTime - pause.time) > 0.5) {
                dismissedPauses.delete(pause.id);
            }
        });
        lastRequestedSeekTime = targetTime;
        lastPlaybackTime = targetTime;
        video.currentTime = targetTime;
        startHlsLoadAt(targetTime);
        updateTimeline();
    }

    function startHlsLoadAt(seconds) {
        if (!hlsPlayer) {
            return;
        }

        const targetTime = Math.max(seconds || 0, 0);
        hlsPlayer.stopLoad();
        hlsPlayer.startLoad(targetTime);
    }

    function restartHlsLoadAtCurrentTime() {
        startHlsLoadAt(lastRequestedSeekTime ?? video.currentTime ?? 0);
    }

    function seekBy(seconds) {
        seekTo((video.currentTime || 0) + seconds);
    }

    function skipCurrentInterjection() {
        const interjectionRange = getCurrentInterjectionRange();
        if (!interjectionRange || !Number.isFinite(interjectionRange.skip_end)) {
            return;
        }

        seekTo(interjectionRange.skip_end);
    }

    function unloadCurrentSource() {
        if (hlsPlayer) {
            hlsPlayer.stopLoad();
            hlsPlayer.destroy();
            hlsPlayer = null;
        }

        video.pause();
        video.removeAttribute('src');
        video.load();
    }

    function loadVideoSource(sourceUrl, startTime, shouldPlay) {
        unloadCurrentSource();
        const targetStartTime = Math.max(startTime || 0, 0);

        video.addEventListener('loadedmetadata', () => {
            video.currentTime = Math.min(targetStartTime, getVideoDuration());
            lastPlaybackTime = video.currentTime || 0;
            updateTimeline();
            if (!showPauseAtCurrentTime() && shouldPlay) {
                playWhenReady();
            }
        }, { once: true });

        if (window.Hls && window.Hls.isSupported()) {
            hlsPlayer = new window.Hls({
                autoStartLoad: false,
                backBufferLength: 10,
                capLevelToPlayerSize: false,
                maxBufferLength: 20,
                startLevel: -1,
                startPosition: targetStartTime,
            });
            hlsPlayer.loadSource(sourceUrl);
            hlsPlayer.attachMedia(video);
            hlsPlayer.on(window.Hls.Events.MANIFEST_PARSED, () => {
                const highestEncodedLevel = hlsPlayer.levels.reduce((bestLevel, level, index) => {
                    if (level.height > 1080) {
                        return bestLevel;
                    }

                    if (bestLevel === -1 || level.height > hlsPlayer.levels[bestLevel].height) {
                        return index;
                    }

                    return bestLevel;
                }, -1);

                if (highestEncodedLevel >= 0) {
                    hlsPlayer.autoLevelCapping = highestEncodedLevel;
                }

                if (qualitySelect.value === 'auto') {
                    hlsPlayer.currentLevel = -1;
                } else {
                    setHlsQuality(qualitySelect.value);
                }

                video.currentTime = Math.min(targetStartTime, getVideoDuration() || targetStartTime);
                lastPlaybackTime = video.currentTime || 0;
                startHlsLoadAt(targetStartTime);
                showPauseAtCurrentTime();
            });
            hlsPlayer.on(window.Hls.Events.ERROR, (_event, data) => {
                if (!data.fatal) {
                    return;
                }

                if (data.type === window.Hls.ErrorTypes.NETWORK_ERROR) {
                    hlsPlayer.startLoad(video.currentTime || 0);
                    return;
                }

                if (data.type === window.Hls.ErrorTypes.MEDIA_ERROR) {
                    hlsPlayer.recoverMediaError();
                }
            });
            return;
        }

        if (video.canPlayType('application/vnd.apple.mpegurl')) {
            video.src = sourceUrl;
            video.load();
        }
    }

    function setHlsQuality(quality) {
        if (!hlsPlayer) {
            return false;
        }

        if (quality === 'auto') {
            hlsPlayer.currentLevel = -1;
            return true;
        }

        const targetHeight = Number.parseInt(quality, 10);
        const targetLevel = hlsPlayer.levels
            .map((level, index) => ({ ...level, index }))
            .find((level) => level.height === targetHeight);
        if (!targetLevel) {
            return false;
        }

        hlsPlayer.currentLevel = targetLevel.index;
        return true;
    }

    function changeQuality(quality) {
        const source = qualitySources.find((candidate) => candidate.quality === quality);
        if (!source || !source.url) {
            return;
        }

        if (setHlsQuality(quality)) {
            return;
        }

        const targetTime = video.currentTime || 0;
        const wasPaused = video.paused;
        loadVideoSource(source.url, targetTime, !wasPaused);
    }

    video.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();

        if (video.paused) {
            playWhenReady();
        } else {
            video.pause();
        }
    });

    videoFrame.addEventListener('mousemove', showControls);
    videoFrame.addEventListener('mouseleave', () => {
        if (!video.paused) {
            controls.classList.remove('is-visible');
        }
        volumeControl.classList.remove('is-open');
        settingsControl.classList.remove('is-open');
    });

    controls.addEventListener('click', (event) => {
        event.stopPropagation();
    });

    interjectionMarkers.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();

        const totalDuration = getVideoDuration();
        const markerBounds = interjectionMarkers.getBoundingClientRect();
        if (totalDuration <= 0 || markerBounds.width <= 0) {
            return;
        }

        const clickPercent = (event.clientX - markerBounds.left) / markerBounds.width;
        seekTo(totalDuration * Math.max(Math.min(clickPercent, 1), 0));
        showControls();
    });

    playToggle.addEventListener('click', () => {
        if (video.paused) {
            playWhenReady();
        } else {
            video.pause();
        }
    });

    scrubber.addEventListener('input', () => {
        scrubbing = true;
        currentTime.textContent = formatTime(Number(scrubber.value));
        updateTimeline();
    });

    scrubber.addEventListener('change', () => {
        scrubbing = false;
        seekTo(Number(scrubber.value));
    });

    volume.addEventListener('input', () => {
        video.volume = Number(volume.value);
        video.muted = video.volume === 0;
    });

    volumeToggle.addEventListener('click', () => {
        volumeControl.classList.toggle('is-open');
        showControls();
    });

    volumeControl.addEventListener('click', (event) => {
        event.stopPropagation();
    });

    settingsToggle.addEventListener('click', () => {
        settingsControl.classList.toggle('is-open');
        showControls();
    });

    settingsControl.addEventListener('click', (event) => {
        event.stopPropagation();
    });

    titleBars.addEventListener('pointerdown', (event) => {
        const skipButton = event.target.closest('.skip-interjection[data-skip-end]');
        if (!skipButton) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();
        seekTo(Number(skipButton.dataset.skipEnd));
    });

    pauseContinue.addEventListener('click', () => {
        const pause = pauses.find((candidate) => Math.abs((video.currentTime || 0) - candidate.time) <= 0.5);
        if (pause) {
            dismissedPauses.add(pause.id);
        }
        pauseOverlay.hidden = true;
        lastPlaybackTime = video.currentTime || 0;
        playWhenReady();
    });

    fullscreenToggle.addEventListener('click', () => {
        if (document.fullscreenElement === fullscreenShell) {
            document.exitFullscreen?.();
        } else {
            fullscreenShell.requestFullscreen?.();
        }
        showControls();
    });

    qualitySelect.addEventListener('change', () => {
        changeQuality(qualitySelect.value);
        showControls();
    });

    speedSelect.addEventListener('change', () => {
        const isCustom = speedSelect.value === 'custom';
        customSpeedControl.hidden = !isCustom;
        if (isCustom) {
            setCustomSpeedFromRate(selectedPresetSpeed);
        } else {
            selectedPresetSpeed = Number(speedSelect.value);
            setPlaybackSpeed(speedSelect.value);
        }
        showControls();
    });

    customSpeed.addEventListener('input', () => {
        speedSelect.value = 'custom';
        customSpeedControl.hidden = false;
        updateCustomSpeed();
        showControls();
    });

    document.addEventListener('keydown', (event) => {
        if (event.target instanceof HTMLInputElement) {
            return;
        }

        if (event.code === 'Space') {
            event.preventDefault();
            if (video.paused) {
                playWhenReady();
            } else {
                video.pause();
            }
        }

        if (event.code === 'ArrowLeft') {
            event.preventDefault();
            seekBy(-5);
        }

        if (event.code === 'ArrowRight') {
            event.preventDefault();
            seekBy(5);
        }

        if (event.code === 'Enter') {
            event.preventDefault();
            skipCurrentInterjection();
        }
    });

    skipInterjection.addEventListener('click', () => {
        skipCurrentInterjection();
    });

    video.addEventListener('loadedmetadata', updateTimeline);
    video.addEventListener('seeking', restartHlsLoadAtCurrentTime);
    video.addEventListener('seeked', () => {
        lastRequestedSeekTime = null;
        updateTimeline();
    });
    video.addEventListener('timeupdate', updateTimeline);
    video.addEventListener('timeupdate', markNaturallyCompletedInterjections);
    video.addEventListener('timeupdate', () => saveProgress(false));
    video.addEventListener('play', () => {
        updatePlayToggle();
        updateControlsVisibility();
        startTimelineAnimation();
    });
    video.addEventListener('pause', () => {
        updatePlayToggle();
        updateControlsVisibility();
        stopTimelineAnimation();
        saveProgress(true);
    });
    video.addEventListener('volumechange', () => {
        volume.value = String(video.volume);
        updateVolumeIcon();
    });
    video.addEventListener('ended', () => saveProgress(true));
    document.addEventListener('fullscreenchange', () => {
        updateFullscreenToggle();
        updateTimeline();
    });
    window.addEventListener('pagehide', () => saveProgress(true));

    renderInitialIcons();
    updatePlayToggle();
    updateFullscreenToggle();
    video.volume = 1;
    video.muted = false;
    setPlaybackSpeed(1);
    volume.value = '1';
    updateVolumeIcon();
    fullscreenShell.style.setProperty('--active-title-bars-height', `${reservedTitleBarsHeight}px`);
    updateTimeline();
    updateControlsVisibility();
    loadVideoSource(video.dataset.mainSrc, savedStartTime, true);
}());
