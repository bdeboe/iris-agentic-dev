use anyhow::Result;
use clap::{Args, Subcommand, ValueEnum};

#[derive(Args)]
pub struct SkillCommand {
    #[command(subcommand)]
    pub subcommand: SkillSubcommand,
}

#[derive(Subcommand)]
pub enum SkillSubcommand {
    /// Install InterSystems skills into AI agent directories (core skills unless --all or names)
    Install(SkillInstallArgs),
    /// List skills in the official pack, their tier and their install status
    List(SkillListArgs),
    /// Show install paths and managed-by status for all local skill files
    Status,
}

#[derive(Args)]
pub struct SkillInstallArgs {
    /// Skill names to install, at any tier (omit for the core skills)
    pub skills: Vec<String>,

    /// Install the core and extra skills, not just core
    #[arg(long, conflicts_with = "skills")]
    pub all: bool,

    /// Remove managed copies of skills this install would not write (left by an older install)
    #[arg(long)]
    pub prune: bool,

    /// Target agent(s)
    #[arg(long, default_value = "all-user-global")]
    pub agent: AgentTarget,

    /// Show what would be installed without writing files
    #[arg(long)]
    pub dry_run: bool,

    /// Overwrite user-authored skills
    #[arg(long)]
    pub force: bool,

    /// Mirror installed skills to a connected IRIS instance
    #[arg(long)]
    pub mirror_to_iris: bool,
}

#[derive(Args)]
pub struct SkillListArgs {
    /// Filter by agent
    #[arg(long)]
    pub agent: Option<AgentTarget>,
}

#[derive(Debug, Clone, ValueEnum, PartialEq, Eq)]
pub enum AgentTarget {
    /// Claude Code only
    #[value(name = "claude-code")]
    ClaudeCode,
    /// OpenCode only
    #[value(name = "opencode")]
    OpenCode,
    /// Copilot (repo-scoped, cwd must be a git repo)
    #[value(name = "copilot")]
    Copilot,
    /// All agents
    #[value(name = "all")]
    All,
    /// Claude Code + OpenCode (user-global; default)
    #[value(name = "all-user-global")]
    AllUserGlobal,
}

impl SkillCommand {
    pub async fn run(self) -> Result<()> {
        match self.subcommand {
            SkillSubcommand::Install(args) => run_install(args).await,
            SkillSubcommand::List(args) => run_list(args),
            SkillSubcommand::Status => run_status(),
        }
    }
}

async fn run_install(args: SkillInstallArgs) -> Result<()> {
    use iris_agentic_dev_core::skill_install::{
        find_leftovers, install_skill, keep_after_fetch, prune_leftovers, select_paths,
        InstallMode, InstallOutcome, SkillPackInstaller,
    };

    if args.mirror_to_iris {
        eprintln!(
            "warning: --mirror-to-iris is not yet implemented; install will proceed to file targets only"
        );
    }

    let mode = if !args.skills.is_empty() {
        InstallMode::Named(args.skills.clone())
    } else if args.all {
        InstallMode::All
    } else {
        InstallMode::Core
    };
    if args.prune && matches!(mode, InstallMode::Named(_)) {
        eprintln!("error: --prune works with a bare install or --all, not with skill names");
        crate::exit(2);
    }

    let installer = SkillPackInstaller::new();

    let skill_paths = installer.fetch_pack_manifest().await?;

    let mut written = 0usize;
    let mut updated = 0usize;
    let mut skipped = 0usize;
    let mut failed = 0usize;

    for (skill_name, skill_path) in select_paths(&skill_paths, &mode) {
        let content = match installer.fetch_skill_content(&skill_path).await {
            Ok(c) => c,
            Err(e) => {
                eprintln!("error: could not fetch {}: {}", skill_name, e);
                failed += 1;
                continue;
            }
        };

        if !keep_after_fetch(&mode, &skill_name, &content) {
            continue;
        }

        let targets = build_targets(&skill_name, &args);

        let results = install_skill(&skill_name, &content, &targets, args.dry_run);

        for result in &results {
            let path_str = result.target.target_path.display();
            match &result.outcome {
                InstallOutcome::Written => {
                    println!("Installing {} → {} ... written", skill_name, path_str);
                    written += 1;
                }
                InstallOutcome::Updated => {
                    println!("Installing {} → {} ... updated", skill_name, path_str);
                    updated += 1;
                }
                InstallOutcome::Skipped => {
                    println!(
                        "Skipped: {} (user-authored — use --force to overwrite)",
                        path_str
                    );
                    skipped += 1;
                }
                InstallOutcome::Failed(msg) => {
                    eprintln!("Failed: {} — {}", path_str, msg);
                    failed += 1;
                }
            }
        }
    }

    println!();
    println!(
        "{} written, {} updated, {} skipped.",
        written, updated, skipped
    );

    let leftovers = find_leftovers(&install_bases(&args.agent), &mode);
    if !leftovers.is_empty() {
        println!();
        if args.prune {
            for (path, r) in prune_leftovers(&leftovers, args.dry_run) {
                match r {
                    Ok(()) if args.dry_run => {
                        println!("Pruning {} ... would remove", path.display())
                    }
                    Ok(()) => println!("Pruning {} ... removed", path.display()),
                    Err(e) => {
                        eprintln!("Failed: {} — {}", path.display(), e);
                        failed += 1;
                    }
                }
            }
        } else {
            let mut names: Vec<&str> = leftovers.iter().map(|(n, _)| n.as_str()).collect();
            names.dedup();
            println!(
                "An older install left {} skill(s) this install does not include: {}",
                names.len(),
                names.join(", ")
            );
            println!(
                "Nothing was deleted. `iris-agentic-dev skill install --prune` removes them (managed copies only); `skill install --all` keeps the extra skills up to date instead."
            );
        }
    }

    if failed > 0 {
        crate::exit(1);
    }
    Ok(())
}

/// The user-global skill directories for `agent`. Copilot's are repo-scoped and committed, so
/// leftovers there are never reported or pruned.
fn install_bases(agent: &AgentTarget) -> Vec<std::path::PathBuf> {
    use iris_agentic_dev_core::skill_install::{claude_code, opencode};
    let mut bases = Vec::new();
    if matches!(
        agent,
        AgentTarget::ClaudeCode | AgentTarget::AllUserGlobal | AgentTarget::All
    ) {
        bases.extend(claude_code::install_base(None));
    }
    if matches!(
        agent,
        AgentTarget::OpenCode | AgentTarget::AllUserGlobal | AgentTarget::All
    ) {
        bases.extend(opencode::install_base(None));
    }
    bases
}

fn build_targets(
    skill_name: &str,
    args: &SkillInstallArgs,
) -> Vec<iris_agentic_dev_core::skill_install::InstallTarget> {
    use iris_agentic_dev_core::skill_install::InstallTarget;

    let mut targets = Vec::new();
    match args.agent {
        AgentTarget::ClaudeCode | AgentTarget::AllUserGlobal | AgentTarget::All => {
            if let Some(t) = InstallTarget::for_claude_code(skill_name, None) {
                targets.push(t);
            }
        }
        _ => {}
    }
    match args.agent {
        AgentTarget::OpenCode | AgentTarget::AllUserGlobal | AgentTarget::All => {
            if let Some(t) = InstallTarget::for_opencode(skill_name, None) {
                targets.push(t);
            }
        }
        _ => {}
    }
    match args.agent {
        AgentTarget::Copilot | AgentTarget::All => {
            let cwd = std::env::current_dir().unwrap_or_else(|_| std::path::PathBuf::from("."));
            if !cwd.join(".git").exists() && !cwd.join(".github").exists() {
                eprintln!(
                    "error: COPILOT_NO_REPO — cwd is not a git repo; copilot install skipped"
                );
            } else {
                targets.push(InstallTarget::for_copilot(skill_name, &cwd));
                eprintln!(
                    "Note: .github/instructions/ is repo-scoped. Commit this directory to share with your team."
                );
            }
        }
        _ => {}
    }
    targets
}

fn run_list(args: SkillListArgs) -> Result<()> {
    use iris_agentic_dev_core::skill_install::InstallTarget;

    let catalog = advertised_catalog();

    let show_cc = matches!(
        args.agent,
        None | Some(AgentTarget::ClaudeCode)
            | Some(AgentTarget::AllUserGlobal)
            | Some(AgentTarget::All)
    );
    let show_oc = matches!(
        args.agent,
        None | Some(AgentTarget::OpenCode)
            | Some(AgentTarget::AllUserGlobal)
            | Some(AgentTarget::All)
    );
    let show_co = matches!(
        args.agent,
        None | Some(AgentTarget::Copilot) | Some(AgentTarget::All)
    );

    println!(
        "{:<34} {:<8} {:<16} {:<14} COPILOT",
        "SKILL", "TIER", "CLAUDE CODE", "OPENCODE"
    );

    for (name, tier) in &catalog {
        let cc = if show_cc {
            InstallTarget::for_claude_code(name, None)
                .map(|t| {
                    if t.target_path.exists() {
                        "installed"
                    } else {
                        "not installed"
                    }
                })
                .unwrap_or("n/a")
        } else {
            "n/a"
        };

        let oc = if show_oc {
            InstallTarget::for_opencode(name, None)
                .map(|t| {
                    if t.target_path.exists() {
                        "installed"
                    } else {
                        "not installed"
                    }
                })
                .unwrap_or("n/a")
        } else {
            "n/a"
        };

        let co = "n/a";
        let _ = show_co;

        println!("{:<34} {:<8} {:<16} {:<14} {}", name, tier, cc, oc, co);
    }

    Ok(())
}

fn run_status() -> Result<()> {
    use iris_agentic_dev_core::skill_install::{is_managed, InstallTarget};

    for (name, _) in advertised_catalog() {
        let name = name.as_str();
        for target in [
            InstallTarget::for_claude_code(name, None),
            InstallTarget::for_opencode(name, None),
        ]
        .into_iter()
        .flatten()
        {
            let path = &target.target_path;
            if path.exists() {
                let managed = if is_managed(path) {
                    "managed"
                } else {
                    "user-authored"
                };
                println!("{}: {} ({})", name, path.display(), managed);
            }
        }
    }

    Ok(())
}

/// `(name, tier)` for every skill this binary ships except the internal tier, core first.
fn advertised_catalog() -> Vec<(String, &'static str)> {
    use iris_agentic_dev_core::skills::bundled::{advertised, load_bundled_skills, SkillTier};
    let mut v: Vec<(String, Option<SkillTier>)> = advertised(&load_bundled_skills())
        .into_iter()
        .map(|s| (s.name, s.tier))
        .collect();
    v.sort_by_key(|(n, t)| (*t != Some(SkillTier::Core), n.clone()));
    v.into_iter()
        .map(|(n, t)| (n, t.map_or("extra", |t| t.as_str())))
        .collect()
}
