use crate::all_json_schema::ALL_JSON_SCHEMAS;
use crate::client::SurfClient;
use crate::pretty_buf::PrettyBuf;
use anyhow::{Context, Result};
use either::Right;
use serde_tombi::config::try_from_path;
use std::borrow::Cow;
use std::path::{Path, PathBuf};
use std::time::Instant;
use tombi_config::{Config, SchemaOptions, CONFIG_FILENAME, PYPROJECT_FILENAME};
use tombi_diagnostic::Print;
use tombi_formatter::formatter::definitions::FormatDefinitions;
use tombi_formatter::Formatter;
use tombi_schema_store::{SchemaSpec, SchemaUrl};

#[derive(Debug)]
pub enum FormatResult {
    Success { formatted_content: String },
    Ignored,
    Error { error: String },
}

pub fn load_with_path(current_dir: &Path) -> Result<(Config, Option<PathBuf>)> {
    let mut current_dir = current_dir.to_path_buf();

    loop {
        let config_path = current_dir.join(CONFIG_FILENAME);
        if config_path.exists() {
            let Some(config) = try_from_path(&config_path)? else {
                unreachable!("tombi.toml should always be parsed successfully.");
            };

            return Ok((config, Some(config_path)));
        }

        let pyproject_toml_path = current_dir.join(PYPROJECT_FILENAME);
        if pyproject_toml_path.exists() {
            if let Some(config) = try_from_path(&pyproject_toml_path)? {
                return Ok((config, Some(pyproject_toml_path)));
            };
        }

        if !current_dir.pop() {
            break;
        }
    }

    Ok((Config::default(), None))
}

pub fn format(
    target_path: PathBuf,
    target_content: String,
    current_dir: PathBuf,
) -> Result<FormatResult> {
    let (mut config, config_path) = load_with_path(&current_dir)?;

    let toml_version = config.toml_version.unwrap_or_default();
    let schema_options = config.schema.as_ref();
    let schema_store = tombi_schema_store::SchemaStore::new_with_client(
        SurfClient::new(),
        tombi_schema_store::Options {
            offline: Some(false),
            strict: schema_options.and_then(|schema_options| schema_options.strict()),
        },
    );

    smol::block_on(async {
        for schema_data in ALL_JSON_SCHEMAS {
            let url = SchemaUrl::parse(schema_data.url)?;
            let content = Cow::Borrowed(schema_data.content);
            let file_match: Vec<String> = serde_json::from_str(schema_data.file_match)?;
            schema_store
                .associate_schema(SchemaSpec::Raw(url, content), file_match)
                .await;
        }

        if config.schema.is_none() {
            config.schema = Some(SchemaOptions {
                enabled: Some(false.into()),
                strict: None,
                catalog: None,
            });
        }

        println!("{:?}", Instant::now());

        schema_store
            .load_config(&config, config_path.as_deref())
            .await?;

        println!("{:?} 0", Instant::now());

        let exclude_patterns: Option<Vec<&str>> = config
            .exclude
            .as_deref()
            .map(|p| p.iter().map(|s| s.as_str()).collect());
        let format_options = config.format.unwrap_or_default();

        if let Some(patterns) = exclude_patterns {
            let exclude_matchers = patterns
                .iter()
                .map(|p| glob::Pattern::new(p).context("Invalid exclude pattern"))
                .collect::<Result<Vec<_>>>()?;

            for matcher in exclude_matchers {
                if matcher.matches_path(&target_path) {
                    return Ok(FormatResult::Ignored);
                }
            }
        }

        let formatter = Formatter::new(
            toml_version,
            FormatDefinitions::default(),
            &format_options,
            Some(Right(&target_path)),
            &schema_store,
        );

        let mut printer = PrettyBuf::new();

        match formatter.format(&target_content).await {
            Ok(formatted) => Ok(FormatResult::Success {
                formatted_content: formatted,
            }),
            Err(diagnostics) => {
                diagnostics
                    .into_iter()
                    .map(|diagnostic| diagnostic.with_source_file(target_path.clone()))
                    .collect::<Vec<_>>()
                    .print(&mut printer);

                Ok(FormatResult::Error {
                    error: printer.get(),
                })
            }
        }
    })
}
