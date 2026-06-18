(function () {
    const video = document.getElementById('lesson-video');
    const videoFrame = video.closest('.video-frame');
    const title = document.getElementById('video-title');
    const controls = document.getElementById('video-controls');
    const playToggle = document.getElementById('video-play-toggle');
    const scrubber = document.getElementById('video-scrubber');
    const interjectionMarkers = document.getElementById('video-interjection-markers');
    const videoProgress = document.getElementById('video-progress');
    const videoPlayhead = document.getElementById('video-playhead');
    const currentTime = document.getElementById('video-current-time');
    const duration = document.getElementById('video-duration');
    const volumeControl = document.getElementById('video-volume-control');
    const volumeToggle = document.getElementById('video-volume-toggle');
    const volume = document.getElementById('video-volume');
    const qualitySelect = document.getElementById('video-quality');
    const skipInterjection = document.getElementById('skip-interjection');

    if (!video || !videoFrame || !title || !controls || !playToggle || !scrubber || !interjectionMarkers || !videoProgress || !videoPlayhead || !currentTime || !duration || !volumeControl || !volumeToggle || !volume || !qualitySelect || !skipInterjection) {
        return;
    }

    const mainTitle = video.dataset.mainTitle;
    const progressUrl = video.dataset.progressUrl;
    const savedStartTime = Math.max(Number(video.dataset.startTime || 0), 0);
    const finishedVideos = new Set(JSON.parse(video.dataset.finishedVideos || '[]'));
    const ranges = JSON.parse(video.dataset.interjections || '[]')
        .filter((range) => Number.isFinite(range.start) && Number.isFinite(range.end) && range.end > range.start)
        .sort((left, right) => left.start - right.start);
    const qualitySources = JSON.parse(video.dataset.qualitySources || '[]');
    const maxMarkerDepth = Math.min(Math.max(...ranges.map((range) => range.depth || 0), 0), 6);
    let timelineAnimationFrame;
    let controlsHideTimer;
    let hlsPlayer = null;
    let lastRequestedSeekTime = null;
    let markerDuration = null;
    let lastProgressSaveTime = 0;
    let lastSavedVideoSecond = savedStartTime;
    let lastPlaybackTime = savedStartTime;
    let scrubbing = false;

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

    function getCurrentInterjectionRange() {
        const time = video.currentTime || 0;
        return ranges
            .filter((range) => range.depth > 0 && time >= range.start && time < range.end)
            .sort((left, right) => right.depth - left.depth)[0] || null;
    }

    function updatePlayToggle() {
        playToggle.innerHTML = video.paused
            ? '<span class="material-symbols-rounded" aria-hidden="true">play_arrow</span>'
            : '<span class="material-symbols-rounded" aria-hidden="true">pause</span>';
        playToggle.setAttribute('aria-label', video.paused ? 'Play' : 'Pause');
    }

    function updateVolumeIcon() {
        let icon = 'volume_up';
        if (video.muted || video.volume === 0) {
            icon = 'volume_off';
        } else if (video.volume < 0.5) {
            icon = 'volume_down';
        }

        volumeToggle.innerHTML = `<span class="material-symbols-rounded" aria-hidden="true">${icon}</span>`;
    }

    function updateTitleAndSkip() {
        const range = getCurrentRange();
        const interjectionRange = getCurrentInterjectionRange();
        title.textContent = range ? range.title : mainTitle;
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
        controls.classList.add('is-visible');
        clearTimeout(controlsHideTimer);

        if (!video.paused && !volumeControl.classList.contains('is-open')) {
            controlsHideTimer = setTimeout(() => {
                controls.classList.remove('is-visible');
            }, 1800);
        }
    }

    function updateControlsVisibility() {
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

    function saveProgress(force = false) {
        if (!progressUrl || !Number.isFinite(video.currentTime)) {
            return;
        }

        const now = Date.now();
        const videoSecond = video.currentTime || 0;
        if (!force && (now - lastProgressSaveTime < 15000 || Math.abs(videoSecond - lastSavedVideoSecond) < 1)) {
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
            if (shouldPlay) {
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

    qualitySelect.addEventListener('change', () => {
        changeQuality(qualitySelect.value);
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
    });

    skipInterjection.addEventListener('click', () => {
        const interjectionRange = getCurrentInterjectionRange();
        if (!interjectionRange || !Number.isFinite(interjectionRange.skip_end)) {
            return;
        }

        seekTo(interjectionRange.skip_end);
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
    window.addEventListener('pagehide', () => saveProgress(true));

    updatePlayToggle();
    video.volume = 1;
    video.muted = false;
    volume.value = '1';
    updateVolumeIcon();
    updateTimeline();
    updateControlsVisibility();
    loadVideoSource(video.dataset.mainSrc, savedStartTime, true);
}());
