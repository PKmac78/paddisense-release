# Definition of Done (DoD)

## A) Code & Structure
- [ ] Change is limited to relevant module(s)
- [ ] No secrets committed
- [ ] Schema version updated if changed
- [ ] Module VERSION updated
- [ ] Version sensor updated (if applicable)
- [ ] Entity IDs preserved OR MAJOR bump + migration notes

## B) UX
- [ ] Mobile-first verified (touch targets, readability)
- [ ] Dark mode verified (no contrast failures)
- [ ] Errors surfaced cleanly (popup where possible, fallback notification)

## C) Offline & Resilience
- [ ] Core workflow works without internet
- [ ] Unavailable sensors handled gracefully
- [ ] Alerts rate-limited (no spam loops)

## D) Multi-user
- [ ] Master edits protected (lock or safe conflict strategy)
- [ ] Operator identity recorded where relevant

## E) Testing (minimum)
- [ ] Fresh install path tested (new HAOS)
- [ ] Upgrade path tested (existing local data preserved)
- [ ] Backup/restore verified for affected module
- [ ] One happy path + one failure path tested

## F) Documentation
- [ ] Relevant module docs updated
- [ ] Install notes updated if needed
- [ ] Changelog notes included if user action required
