# Reflection (300–500 words)

I used Claude desktop and Claude Code for this project, and downloaded skills for Claude Code as I got familiar with it. This was my first time vibe coding and building something like this. I coached the AI through the project and learned a lot about how to build and format a Streamlit app through GitHub, and how to organize data through an app.

We built a Streamlit-hosted website with a live Gemini agent that calls our functions to answer questions, with a rules-based backup when the API fails. We used the free tier of the Gemini API, which has limits. When we tested it today, Gemini's server was busy and the backup answered most questions instead. The numbers were still right, but that is a real limit of this setup.

The hardest part was validating that everything was working right, and following the assignment given how complex it is. I also struggled to understand the meaning behind what I was changing, but I got to the original goal anyway.

One bug I remember is from Test 2. We asked which store had the biggest decline, and the app showed revenue share data instead. The word "percentage" threw off the system and sent the question to the wrong calculation. We changed the rules so decline words come first. After that we retested it, and it named Chicago, down 66.81%.

AI helped a lot. Where I messed up was making the app too complicated early on. It kept breaking, and I had to go back to simpler formatting the more I played around with it.

My own judgment mattered most in how much sense the app made and how the site was designed: where the Ask page goes and where data validation goes. Rather than a yellow box on the main page, I made a tab just for that.

Because there are no costs in the data, estimating profit is impossible without more data. It's still a helpful app without that, it's just limited in forecasting. I'd trust it for a first look, not a final decision. Before using it for a real business decision I'd want to validate the code further through AI code review, someone else's AI system, or a professional. I made something that works, but I'm not confident it's perfect.

# Contribution statement
| Team member | Main responsibilities | Key calculation or design decision I can explain | Approximate commits |
|---|---|---|---|
| Mike O'Shaughnessy | Directed the AI through the full build, tested and validated the app, deployed through GitHub and Streamlit, made the layout and design calls | The $1,000 test, and moving data validation off the main page into its own tab | About 20 |
