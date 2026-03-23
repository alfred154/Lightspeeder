@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.lower()
    user_id = message.author.id

    # -----------------------------
    # HELP MENU
    # -----------------------------
    if bot.user in message.mentions and "help" in content:
        await message.reply(HELP_TEXT)
        return

    # -----------------------------
    # ACTIVE TROUBLESHOOTING SESSION (HYBRID MODE)
    # -----------------------------
    session = get_session(user_id)
    if session:
        # User controls the flow
        if content.strip() == "next":
            next_step = advance_session(user_id)
            if next_step == "done":
                await message.reply("All steps completed.\n\n" + ESCALATION_CONTACTS)
            else:
                await message.reply(
                    f"**Step {session['index']+1}/{len(session['steps'])}:**\n{next_step}"
                )
            return

        if content.strip() == "stop":
            stop_session(user_id)
            await message.reply("Troubleshooting cancelled.")
            return

        # Detect if user is trying to start a NEW hardware issue
        new_hw = detect_hardware_category(content)
        if new_hw:
            await message.reply(
                f"You're already troubleshooting the **{session['category']}**.\n"
                "Say **next** to continue or **stop** to cancel."
            )
            return

        # Detect if user is asking a QUESTION
        def is_question(text):
            return "?" in text or any(
                text.startswith(q) for q in ["how", "what", "why", "where", "when"]
            )

        if is_question(content):
            # Answer normally using handbook
            title, body = find_best_section(content)
            if title and body:
                if len(body) > 1500:
                    body = body[:1500] + "\n\n...(truncated)..."

                await message.reply(
                    f"**{title.title()}**\n\n{body}\n\n"
                    f"You're still in **{session['category']} troubleshooting** — say **next** to continue."
                )
                return

            await message.reply(
                "I couldn't find anything in the handbook for that question.\n\n"
                f"You're still in **{session['category']} troubleshooting** — say **next** to continue."
            )
            return

        # Any other message → answer normally + reminder
        title, body = find_best_section(content)
        if title and body:
            if len(body) > 1500:
                body = body[:1500] + "\n\n...(truncated)..."

            await message.reply(
                f"**{title.title()}**\n\n{body}\n\n"
                f"You're still in **{session['category']} troubleshooting** — say **next** to continue."
            )
            return

        await message.reply(
            f"You're still in **{session['category']} troubleshooting** — say **next** to continue or **stop** to cancel."
        )
        return

    # -----------------------------
    # DISTANCE TOOL
    # -----------------------------
    if bot.user in message.mentions and "distance" in content:
        try:
            cleaned = (
                message.content
                .replace(f'<@{bot.user.id}>', '')
                .replace(f'<@!{bot.user.id}>', '')
                .strip()
            )

            if " to " not in cleaned:
                await message.reply("Format: `@Bot distance from LOCATION1 to LOCATION2`")
                return

            loc1, loc2 = cleaned.split(" to ", 1)
            loc1 = loc1.replace("distance", "").replace("from", "").strip()
            loc2 = loc2.strip()

            await message.channel.typing()

            straight, drive_minutes, p1, p2 = await get_distance_between_locations(loc1, loc2)
            if straight is None:
                await message.reply("I couldn't find one of those locations.")
                return

            hours = drive_minutes // 60
            mins = drive_minutes % 60

            await message.reply(
                f"{loc1.title()} to {loc2.title()}\n"
                f"Distance: {straight:.1f} Miles\n"
                f"Drive Time: {hours}h {mins:02d}min"
            )
            return

        except Exception as e:
            await message.reply(f"Error calculating distance: {e}")
            return

    # -----------------------------
    # NEW LIGHTSPEED QUESTION OR TROUBLESHOOTING
    # -----------------------------
    if bot.user in message.mentions:
        query = (
            message.content
            .replace(f'<@{bot.user.id}>', '')
            .replace(f'<@!{bot.user.id}>', '')
            .strip()
        )

        # Detect hardware category
        category = detect_hardware_category(query)

        # Hardware → start troubleshooting
        if category:
            title, body = find_best_section(query)
            steps = extract_steps(body) if body else []

            if not steps:
                steps = fallback_steps(category)

            start_session(user_id, category, steps)

            await message.reply(
                f"**{category.title()} Troubleshooting — Step 1/{len(steps)}**\n{steps[0]}\n\n"
                "Say **next** when done or **stop** to cancel."
            )
            return

        # Normal Q&A
        title, body = find_best_section(query)
        if title and body:
            if len(body) > 1500:
                body = body[:1500] + "\n\n...(truncated)..."
            await message.reply(f"**{title.title()}**\n\n{body}")
            return

        await message.reply("I couldn't find anything in the Lightspeed handbook for that question.")
        return

    await bot.process_commands(message)
