
pub struct SchemaData {
    pub url: String,
    pub file_match: Vec<String>,
    pub content: String
}

pub struct EmbeddedSchemaData {
    pub url: &'static str,
    pub file_match: &'static str,
    pub content: &'static str
}
