from tools.research import search_and_read


def research_saas(goal: str) -> dict:
    return {
        "stack": search_and_read(f"best SaaS tech stack for {goal} in 2025"),
        "build_speed": search_and_read(f"fastest way to build {goal} SaaS solo developer 2025"),
        "competitors": search_and_read(f"{goal} SaaS competitors analysis"),
    }

