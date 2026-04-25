from tools.deployer import deploy_to_netlify, deploy_to_vercel


def deploy_saas(project_dir: str, project_name: str, platform: str = "vercel") -> str:
    if platform == "netlify":
        return deploy_to_netlify(project_dir, project_name)
    return deploy_to_vercel(project_dir, project_name)
