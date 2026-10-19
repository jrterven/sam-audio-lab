import { useEffect, useRef, useState, type RefObject } from "react";

export function usePlayback(
  audio: HTMLAudioElement | null,
  video: RefObject<HTMLVideoElement | null>,
  url: string,
  scope: string,
  duration: number,
  onError: (message: string) => void,
) {
  const [current, setCurrent] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const position = useRef(0);
  const requestedPlay = useRef(false);
  const changingSource = useRef(false);
  const previousScope = useRef("");
  const generation = useRef(0);
  const length = useRef(duration);
  length.current = duration;

  const seek = (time: number) => {
    const next = Math.max(0, Math.min(time, length.current));
    position.current = next;
    setCurrent(next);
    if (audio && audio.readyState > 0) audio.currentTime = next;
    if (video.current && video.current.readyState > 0)
      video.current.currentTime = next;
  };

  const resume = async (token: number) => {
    if (!audio || !requestedPlay.current || changingSource.current) return;
    // A track selected at the end of another track must still be playable.
    if (audio.ended || audio.currentTime >= length.current - 0.04) seek(0);
    try {
      await audio.play();
      if (token !== generation.current || !requestedPlay.current) return;
      if (video.current) {
        video.current.currentTime = audio.currentTime;
        await video.current.play();
      }
    } catch (error) {
      if (token !== generation.current || !requestedPlay.current) return;
      requestedPlay.current = false;
      audio.pause();
      video.current?.pause();
      setPlaying(false);
      onError((error as Error).message);
    }
  };

  useEffect(() => {
    if (!audio) return;
    const sync = () => {
      if (changingSource.current) return;
      position.current = audio.currentTime;
      setCurrent(audio.currentTime);
      if (
        video.current &&
        Math.abs(video.current.currentTime - audio.currentTime) > 0.12
      )
        video.current.currentTime = audio.currentTime;
    };
    const started = () => setPlaying(true);
    const stopped = () => {
      if (changingSource.current) return;
      requestedPlay.current = false;
      setPlaying(false);
      video.current?.pause();
    };
    audio.addEventListener("timeupdate", sync);
    audio.addEventListener("play", started);
    audio.addEventListener("pause", stopped);
    audio.addEventListener("ended", stopped);
    return () => {
      audio.removeEventListener("timeupdate", sync);
      audio.removeEventListener("play", started);
      audio.removeEventListener("pause", stopped);
      audio.removeEventListener("ended", stopped);
    };
  }, [audio]);

  useEffect(() => {
    if (!audio) return;
    const token = ++generation.current;
    const sameScope = previousScope.current === scope;
    position.current = sameScope
      ? changingSource.current
        ? position.current
        : audio.currentTime
      : 0;
    requestedPlay.current = sameScope && requestedPlay.current;
    previousScope.current = scope;
    changingSource.current = true;
    audio.pause();
    video.current?.pause();
    setPlaying(false);
    setCurrent(position.current);
    setLoading(!!url);
    const loaded = () => {
      if (token !== generation.current) return;
      seek(position.current);
      changingSource.current = false;
      setLoading(false);
      void resume(token);
    };
    const failed = () => {
      if (token !== generation.current) return;
      changingSource.current = false;
      requestedPlay.current = false;
      setLoading(false);
      setPlaying(false);
      onError(
        "Could not load the audio. Try preparing the clip or uploading the file again.",
      );
    };
    audio.addEventListener("loadedmetadata", loaded);
    audio.addEventListener("error", failed);
    if (url) audio.src = url;
    else audio.removeAttribute("src");
    audio.load();
    return () => {
      ++generation.current;
      audio.removeEventListener("loadedmetadata", loaded);
      audio.removeEventListener("error", failed);
    };
  }, [audio, url, scope]);

  const play = () => {
    if (!audio || !url) return;
    if (requestedPlay.current) {
      requestedPlay.current = false;
      audio.pause();
      video.current?.pause();
      setPlaying(false);
    } else {
      requestedPlay.current = true;
      void resume(generation.current);
    }
  };

  return { current, playing, loading, seek, play };
}
