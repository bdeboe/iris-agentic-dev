use anyhow::Result;

/// List all iris-agentic-dev-* binaries discovered on PATH.
pub fn list_plugins() {
    let prefix = "iris-agentic-dev-";
    let paths = std::env::var("PATH").unwrap_or_default();
    let mut plugins = vec![];
    for dir in std::env::split_paths(&paths) {
        if let Ok(entries) = std::fs::read_dir(&dir) {
            for entry in entries.flatten() {
                let name = entry.file_name().to_string_lossy().to_string();
                if let Some(cmd) = name.strip_prefix(prefix) {
                    plugins.push((cmd.to_string(), entry.path()));
                }
            }
        }
    }
    plugins.sort();
    plugins.dedup_by_key(|(name, _)| name.clone());
    if plugins.is_empty() {
        println!("No iris-agentic-dev-* plugins found on PATH.");
    } else {
        println!("Discovered plugins:");
        for (name, path) in plugins {
            println!("  {} → {}", name, path.display());
        }
    }
}

/// If a binary named iris-agentic-dev-{cmd} exists on PATH, exec it with the remaining args.
/// Never returns on Unix (process is replaced). Returns Ok on Windows after child exits.
pub fn try_dispatch_plugin(cmd: &str, args: &[String]) -> Result<()> {
    let binary = format!("iris-agentic-dev-{}", cmd);
    match which::which(&binary) {
        Ok(path) => {
            #[cfg(unix)]
            {
                use std::os::unix::process::CommandExt;
                let err = std::process::Command::new(&path).args(args).exec();
                anyhow::bail!("failed to exec {}: {}", path.display(), err);
            }
            #[cfg(not(unix))]
            {
                let status = std::process::Command::new(&path).args(args).status()?;
                crate::exit(status.code().unwrap_or(1));
            }
        }
        Err(_) => {
            eprintln!(
                "iris-agentic-dev: unknown command '{}'\nRun `iris-agentic-dev --help` for available commands.",
                cmd
            );
            crate::exit(1);
        }
    }
}
