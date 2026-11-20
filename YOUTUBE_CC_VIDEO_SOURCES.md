# YouTube Creative Commons video sources

NEXORA's `/clipsource <title>` command can optionally discover public YouTube videos whose YouTube Data API metadata reports the Creative Commons Attribution (CC BY) license.

## Enable discovery

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a project.
3. Enable **YouTube Data API v3** for that project.
4. Create an API key under APIs & Services → Credentials.
5. Restrict the key to YouTube Data API v3 and, where practical, to the server environment.
6. Add the key to the Render service as an environment variable named `YOUTUBE_DATA_API_KEY`. Do not paste the key into Telegram, GitHub source files, or ChatGPT.

YouTube API search quota is limited; use the key only for source discovery. If the variable is absent or the API is unavailable, `/clipsource` continues with Wikimedia Commons and Europeana.

## Reuse and safety rules

- The search filters for `videoLicense=creativeCommon`; the video details endpoint is checked again for `creativeCommon`, public visibility, and embeddability.
- A CC BY label is not proof that the uploader owns every image, soundtrack, or third-party clip inside the video. Check the original creator and all included rights before reuse.
- Keep attribution: creator/channel, video title, source URL, and CC BY license.
- NEXORA deliberately does **not** download or extract YouTube streams. The result is a source link only. To use footage in an MP4, obtain the original media file from the creator or another authorized download source and retain evidence of the license/permission.
- Standard YouTube License videos are not treated as reusable footage. Credit alone, short duration, or a “no copyright intended” disclaimer does not grant permission.
- The current implementation is discovery-only: it does not automatically place YouTube footage into rendered videos.

Official references:
- [YouTube license types](https://support.google.com/youtube/answer/2797468)
- [YouTube Data API search.list](https://developers.google.com/youtube/v3/docs/search/list)
- [YouTube Data API videos.list](https://developers.google.com/youtube/v3/docs/videos/list)
- [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/)
