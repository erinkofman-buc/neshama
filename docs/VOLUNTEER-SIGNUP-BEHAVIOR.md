# Volunteer Signup Behavior

How meal signups work for volunteers on Neshama shiva pages.

---

## What Volunteers CAN Do

### Sign up for a meal
- Tap any open slot (Lunch or Dinner on a specific date) to sign up
- Provide: name, email, phone (optional), what they're bringing, number of servings, whether they'll help serve
- After signing up, the shiva address is revealed to them (privacy protection -- address is hidden until someone commits to helping)
- They get a confirmation screen with the address and a link to add it to Google Calendar

### Cancel their own signup
- A "Cancel my signup" button appears on any slot the volunteer signed up for (in that same browser session)
- When they cancel, a confirmation dialog says: "Cancel your meal signup? The organizer will be notified so they can find a replacement."
- The signup is soft-deleted (marked as "cancelled" in the database, not permanently removed)
- The slot immediately reopens for someone else to sign up

### Sign up for alternative contributions
- Instead of a meal, volunteers can offer alternatives (e.g., paper goods, drinks) using a checkbox in the signup form

---

## What Volunteers CANNOT Do

### Edit a signup through the UI
- There is NO edit button in the volunteer view. The backend has an edit endpoint (it can update meal description, servings, will-serve, and phone number), but there is no button or form in the frontend that calls it.
- **If a volunteer needs to change what they're bringing or switch dates, they must cancel and re-sign up.**

### Change the date or meal type of an existing signup
- Even the backend edit endpoint does not support changing the date or switching between Lunch and Dinner. Those fields are not editable -- only meal description, servings, will-serve, and phone can be updated via the API.

### See other volunteers' full names or contact info
- Only first names are shown to other visitors. Full details are only visible to the organizer.

---

## How Organizer Notifications Work for Cancellations

When a volunteer cancels their signup:

1. **Immediate email** -- The organizer gets an email right away via SendGrid with the subject line "Meal cancellation -- [Volunteer Name] for [Date]". The email tells them which meal slot is now open and includes a button to view the meal schedule.

2. **Database record** -- A "volunteer_cancellation" entry is also logged in the email_log table for recordkeeping.

3. **The organizer does NOT need to do anything** to process the cancellation -- it happens automatically. But they may want to share the page again to find a replacement.

---

## How Organizer Removal Works (for comparison)

- The organizer can remove any signup from their dashboard using a "Remove" button
- When the organizer removes a signup, the volunteer is NOT notified (the confirmation dialog says: "Remove this signup? The volunteer will not be notified.")
- Organizer removals are hard-deleted (permanently removed from the database), unlike volunteer cancellations which are soft-deleted

---

## Important Technical Details

- **Session-based ownership**: The system tracks which signups belong to the current visitor using sessionStorage in the browser. This means if a volunteer signs up on their phone and later opens the page on their laptop, they will NOT see the cancel button on the laptop. They would need to contact the organizer to remove it.
- **Email verification on cancel**: When a volunteer cancels, the system verifies that the stored email matches the signup record. This prevents someone from cancelling another person's signup.
- **No login required**: Volunteers do not create accounts. Identity is based on the email they enter at signup time, stored temporarily in their browser session.
