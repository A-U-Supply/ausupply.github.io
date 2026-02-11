# How to Edit This Website

This guide walks you through editing pages on the site using **GitHub Desktop** — the free app from GitHub that lets you work with code without touching the command line.

You'll learn how to:

1. Install GitHub Desktop and clone the site
2. Create a branch (so your changes don't go live immediately)
3. Edit HTML pages
4. Preview your changes locally
5. Push your branch and open a pull request for review

---

## Before You Start: What's Safe?

**The short version: you basically can't break anything permanently.** Git tracks every change ever made, so anything can be undone. Here are some ground rules to make your life easier:

**Totally safe — do these freely:**

- Edit any `.html` file (that's the whole point!)
- Add new images to the `img/` folder
- Create new `.html` files
- Commit as often as you want (more commits = more checkpoints to go back to)
- Create as many branches as you want
- Open pull requests — they're just proposals, nothing goes live until you merge
- Delete a branch you don't need anymore (your commits are still in git history)

**Safe, but be thoughtful:**

- Renaming or deleting files — other pages might link to them. If you're unsure, search for the filename in other `.html` files before removing it
- Editing `vcfmw.css` — this is the shared stylesheet, so changes here affect the look of most pages. Prefer making page-specific style changes inside the HTML file itself

**The one thing to avoid:**

- Don't edit directly on the `master` branch. Always make a new branch first. The `master` branch *is* the live site — so changes there go live immediately with no review step. (If you accidentally do this, don't panic — we can always fix it.)

**If something goes wrong:** Don't worry. Git keeps the full history of every change. Anything can be reverted, restored, or undone. Just ask for help and we'll sort it out.

---

## Step 1: Install GitHub Desktop

1. Go to [desktop.github.com](https://desktop.github.com/) and download the app
2. Open it and sign in with the GitHub account that has access to this repository

> **Note:** You need to be signed in with an account that is an admin or collaborator on the `A-U-Supply/ausupply.github.io` repository.

---

## Step 2: Clone the Repository

"Cloning" downloads a copy of the website's files to your computer so you can edit them.

1. In GitHub Desktop, click **File → Clone Repository** (or the big **"Clone a Repository"** button if this is your first time)
2. Click the **URL** tab
3. Paste in: `A-U-Supply/ausupply.github.io`
4. Choose where on your computer you'd like to save it (the default is fine)
5. Click **Clone**

This downloads all the site's files. You only need to do this once — after cloning, GitHub Desktop remembers the repo.

---

## Step 3: Create a New Branch

A "branch" is like a draft copy of the site. You make your changes on the branch, preview them, and only merge them into the live site when you're happy.

1. In GitHub Desktop, look at the top of the window — you'll see a dropdown that says **"master"** (that's the live version of the site)
2. Click that dropdown
3. Type a name for your branch — something short that describes what you're doing, like:
   - `update-contact-page`
   - `add-new-show-dates`
   - `fix-typo-on-homepage`
4. Click **"Create New Branch"**

You're now working on your own branch. Any changes you make won't affect the live site until you choose to merge them.

---

## Step 4: Open and Edit HTML Files

### Finding the files

All the website's pages are HTML files in the **root folder** (the top-level folder, not inside any subfolder). Here are some key ones:

| File | What it is |
|------|-----------|
| `index.html` | The homepage |
| `contact.html` | Contact page |
| `sketchbook.html` | Sketchbook page |
| `notes.html` | Notes page |
| `this-song-is-a-junkyard.html` | Song titles page |

### Opening the files

1. In GitHub Desktop, click **"Show in Finder"** (Mac) or **"Show in Explorer"** (Windows) to open the folder with all the files
2. Right-click the `.html` file you want to edit
3. Open it with a text editor:
   - **Recommended:** Download [Visual Studio Code](https://code.visualstudio.com/) (free) — it color-codes HTML which makes it much easier to read
   - **Mac fallback:** TextEdit works, but switch to plain text mode first (Format → Make Plain Text)
   - **Windows fallback:** Notepad works in a pinch

### Making changes

HTML files contain the content of each page. Here's a quick crash course on the bits you'll want to edit:

**Text content** lives between tags. For example:

```html
<p>This is a paragraph of text on the page.</p>
```

To change the text, edit the words between the `>` and `<`:

```html
<p>Here is my updated text!</p>
```

**Headings** look like this:

```html
<h1>Big Heading</h1>
<h2>Smaller Heading</h2>
```

**Links** look like this:

```html
<a href="https://example.com">Click here</a>
```

- The URL inside `href="..."` is where the link goes
- The text between `>` and `</a>` is what the link says on the page

**Images** look like this:

```html
<img src="img/photo.png">
```

To add a new image: copy it into the `img/` folder, then update `src="..."` to match the filename.

> **Tip:** If you're not sure which part of the HTML controls what on the page, just change some text, save, and preview (next step). You'll quickly see what moved.

---

## Step 5: Preview Your Changes

You can see exactly what your changes look like before anything goes live:

1. Find the `.html` file you edited in Finder or Explorer
2. Double-click it — it opens in your web browser
3. Check that your changes look right

> **Heads up:** YouTube embeds won't play when previewing locally (you'll see a playback error). That's normal and expected — they work fine once the site is deployed.

If something looks wrong, go back to your text editor, fix it, save, and refresh the browser page.

---

## Step 6: Commit Your Changes

A "commit" is like a save point — a snapshot of your changes with a short note about what you did.

1. Go back to **GitHub Desktop**
2. On the left side, you'll see a list of files you changed (with green and red highlights showing additions and removals)
3. Make sure the checkbox is ticked next to each file you want to include
4. At the bottom left, type a short description in the **"Summary"** box:
   - `Update show dates on homepage`
   - `Fix phone number on contact page`
   - `Add new sketchbook images`
5. Click the blue **"Commit to [your-branch-name]"** button

You can make multiple commits — for example, one per page you edit. Think of each commit as a save point you can return to.

---

## Step 7: Push Your Branch

"Pushing" uploads your commits from your computer to GitHub so others can see them.

1. After committing, you'll see a button at the top that says **"Publish branch"** (first time) or **"Push origin"** (after that)
2. Click it

Your changes are now on GitHub, but still only on your branch — the live site hasn't changed.

---

## Step 8: Open a Pull Request

A "pull request" (PR) is how you propose merging your changes into the live site. It gives you a chance to review everything before it goes live.

1. After pushing, GitHub Desktop will show a blue banner: **"Create a Pull Request from your current branch"** — click it. This opens GitHub in your browser.
   - If you miss the banner: go to the [repository on GitHub.com](https://github.com/A-U-Supply/ausupply.github.io) and you'll see a yellow banner with a **"Compare & pull request"** button
2. Fill in the form:
   - **Title:** A short summary (e.g., "Update contact page info")
   - **Description:** Optional notes about what you changed
3. Click **"Create pull request"**

### Reviewing and merging

- The pull request page shows a "diff" of exactly what changed (green = added, red = removed)
- Look it over, and if you're happy, click the green **"Merge pull request"** button
- Your changes will be live on the site within a minute or two

> **Changed your mind?** You can close a pull request without merging. Nothing happens to the live site. You can also keep pushing more commits to the same branch — the PR updates automatically.

---

## Quick Reference

| I want to... | Do this |
|---|---|
| Start editing | Make sure you're on your branch, not `master` |
| Preview changes | Double-click the `.html` file to open in browser |
| Save a checkpoint | Commit in GitHub Desktop |
| Upload to GitHub | Push (top button in GitHub Desktop) |
| Propose changes for the live site | Open a pull request |
| Make changes go live | Merge the pull request on GitHub.com |
| Start a new task | Create a new branch from `master` |

---

## Tips

- **Always create a new branch** before editing. The `master` branch is the live site.
- **One branch per task.** Updating the contact page and adding show dates? Use two branches. It keeps things clean.
- **Commit often.** Each commit is a save point you can go back to.
- **Don't worry about mistakes.** Git tracks everything. Nothing is permanent, and anything can be undone. Just ask for help.
