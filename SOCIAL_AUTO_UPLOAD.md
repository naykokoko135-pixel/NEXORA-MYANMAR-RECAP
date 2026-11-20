# NEXORA Social Auto-Upload — implementation plan

## Current state

NEXORA can render platform-specific MP4 files, but it does **not** publish them.
The new `social_publishing.py` module is a fail-closed readiness/preflight layer.
It does not call any social API. All platform switches default to OFF.

## Required official integrations

### YouTube
- Official YouTube Data API `videos.insert` resumable upload.
- OAuth 2.0 refresh-token flow with the `youtube.upload` scope.
- Render secrets: `YOUTUBE_UPLOAD_CLIENT_ID`, `YOUTUBE_UPLOAD_CLIENT_SECRET`,
  `YOUTUBE_UPLOAD_REFRESH_TOKEN`.
- A channel owner must authorize the app. Verify upload quota and the channel's
  current API project restrictions before enabling.

### Facebook Page
- Official Meta Graph API Page video publishing endpoint.
- Page access token for a person with the Page's `CREATE_CONTENT` task.
- Permissions: `pages_manage_posts`, `pages_read_engagement`,
  `pages_show_list`; app review/business verification may apply.
- Render secrets: `FACEBOOK_PAGE_ACCESS_TOKEN`, `FACEBOOK_PAGE_ID`.
- Reels and standard Page video publishing have different request flows; select
  the format explicitly rather than silently converting one to the other.

### TikTok
- Official TikTok Content Posting API Direct Post flow.
- Developer app with Content Posting API enabled and approved `video.publish`
  scope; the creator must authorize the app.
- Query creator info before each post, honor returned privacy options and limits,
  initialize the post, upload the MP4, then poll publish status.
- Render secrets: `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`,
  `TIKTOK_ACCESS_TOKEN`, `TIKTOK_OPEN_ID`.
- TikTok unaudited clients are restricted to private visibility. Public posting
  requires TikTok's audit/approval; API availability does not guarantee reach.

## Safety gates and switches

All switches default to OFF:
- `SOCIAL_PUBLISHING_ENABLED=true`
- `YOUTUBE_PUBLISH_ENABLED=true`
- `FACEBOOK_PUBLISH_ENABLED=true`
- `TIKTOK_PUBLISH_ENABLED=true`

Before any upload, NEXORA must require:
1. A non-empty MP4 file.
2. Creator confirmation that script, footage, images, music, and other assets
   are owned, licensed, public-domain, or otherwise specifically authorized.
3. Human review of the finished MP4, title, caption, and platform format.
4. A separate explicit confirmation to publish to the selected account.

The preflight code does not expose credential values and does not send anything.
Platform adapters, OAuth callback/token refresh, upload progress, retry handling,
status polling, and audit logs are a separate implementation phase. Do not enable
the switches until those adapters have passed private/draft tests and each
platform's approval requirements are met.

## Official references

- YouTube upload: https://developers.google.com/youtube/v3/guides/uploading_a_video
- YouTube videos.insert: https://developers.google.com/youtube/v3/docs/videos/insert
- Meta Page videos: https://developers.facebook.com/docs/graph-api/reference/page/videos/
- Meta Page Reels: https://developers.facebook.com/docs/graph-api/reference/page/video_reels/
- TikTok Direct Post: https://developers.tiktok.com/doc/content-posting-api-reference-direct-post
- TikTok Direct Post getting started: https://developers.tiktok.com/doc/content-posting-api-get-started
