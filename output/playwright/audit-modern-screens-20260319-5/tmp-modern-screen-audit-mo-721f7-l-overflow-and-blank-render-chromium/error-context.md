# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - main [ref=e2]:
    - region "Session boundaries start here." [ref=e3]:
      - paragraph [ref=e4]: Authentication
      - heading "Session boundaries start here." [level=1] [ref=e5]
      - paragraph [ref=e6]: Use a governed sign-in path. Sessions are issued server-side, stored in secure HttpOnly cookies, and checked on every protected route.
      - generic [ref=e7]:
        - generic [ref=e8]: Public route
        - generic [ref=e9]: Keyboard-first
        - generic [ref=e10]: Dark-first
        - generic [ref=e11]: Env test
      - 'button "Theme preference: System (Dark). Click to switch to Dark." [ref=e13] [cursor=pointer]':
        - img [ref=e15]
      - generic [ref=e17]:
        - link "Sign in with OIDC" [ref=e18] [cursor=pointer]:
          - /url: /auth/login
        - link "View health route" [ref=e19] [cursor=pointer]:
          - /url: /health
      - generic [ref=e20]:
        - generic [ref=e21]: Dev sign-in identity
        - combobox "Dev sign-in identity" [ref=e22]:
          - option "Fixture Admin (ADMIN)" [selected]
          - option "Fixture Auditor (AUDITOR)"
        - button "Sign in with dev fixture" [ref=e23] [cursor=pointer]
  - alert [ref=e24]
```