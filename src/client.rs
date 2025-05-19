use bytes::Bytes;
use surf::middleware::Redirect;
use surf::utils::async_trait;
use tombi_schema_store::HttpClient;

#[derive(Debug)]
pub struct SurfClient(surf::Client);

impl SurfClient {
    pub fn new() -> Self {
        Self(surf::Client::new())
    }
}

#[async_trait]
impl HttpClient for SurfClient {
    async fn get_bytes(&self, url: &str) -> Result<Bytes, String> {
        let mut response = self
            .0
            .get(url)
            .middleware(Redirect::default())
            .send()
            .await
            .map_err(|err| err.to_string())?;

        let bytes = response.body_bytes().await.map_err(|err| err.to_string())?;

        Ok(Bytes::from(bytes))
    }
}
