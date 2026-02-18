<br />

<br />

# Gemini API

| We have updated our[Terms of Service](https://ai.google.dev/gemini-api/terms).

The fastest path from prompt to production with Gemini, Veo, Nano Banana, and more.  

### Python

    from google import genai

    client = genai.Client()

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents="Explain how AI works in a few words",
    )

    print(response.text)

### JavaScript

    import { GoogleGenAI } from "@google/genai";

    const ai = new GoogleGenAI({});

    async function main() {
      const response = await ai.models.generateContent({
        model: "gemini-2.5-flash",
        contents: "Explain how AI works in a few words",
      });
      console.log(response.text);
    }

    await main();

### Go

    package main

    import (
        "context"
        "fmt"
        "log"
        "google.golang.org/genai"
    )

    func main() {
        ctx := context.Background()
        client, err := genai.NewClient(ctx, nil)
        if err != nil {
            log.Fatal(err)
        }

        result, err := client.Models.GenerateContent(
            ctx,
            "gemini-2.5-flash",
            genai.Text("Explain how AI works in a few words"),
            nil,
        )
        if err != nil {
            log.Fatal(err)
        }
        fmt.Println(result.Text())
    }

### Java

    package com.example;

    import com.google.genai.Client;
    import com.google.genai.types.GenerateContentResponse;

    public class GenerateTextFromTextInput {
      public static void main(String[] args) {
        Client client = new Client();

        GenerateContentResponse response =
            client.models.generateContent(
                "gemini-2.5-flash",
                "Explain how AI works in a few words",
                null);

        System.out.println(response.text());
      }
    }

### C#

    using System.Threading.Tasks;
    using Google.GenAI;
    using Google.GenAI.Types;

    public class GenerateContentSimpleText {
      public static async Task main() {
        var client = new Client();
        var response = await client.Models.GenerateContentAsync(
          model: "gemini-2.5-flash", contents: "Explain how AI works in a few words"
        );
        Console.WriteLine(response.Candidates[0].Content.Parts[0].Text);
      }
    }

### REST

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" \
      -H "x-goog-api-key: $GEMINI_API_KEY" \
      -H 'Content-Type: application/json' \
      -X POST \
      -d '{
        "contents": [
          {
            "parts": [
              {
                "text": "Explain how AI works in a few words"
              }
            ]
          }
        ]
      }'

[Start building](https://ai.google.dev/gemini-api/docs/quickstart)  
Follow our Quickstart guide to get an API key and make your first API call in minutes.

*** ** * ** ***

## Meet the models

[auto_awesomeGemini 3 Pro
Our most intelligent model, the best in the world for multimodal understanding, all built on state-of-the-art reasoning.](https://ai.google.dev/gemini-api/docs/models#gemini-3-pro)[sparkGemini 3 Flash
Frontier-class performance rivaling larger models at a fraction of the cost.](https://ai.google.dev/gemini-api/docs/models#gemini-3-flash)[🍌Nano Banana and Nano Banana Pro
State-of-the-art image generation and editing models.](https://ai.google.dev/gemini-api/docs/image-generation)[sparkGemini 2.5 Pro
Our powerful reasoning model, which excels at coding and complex reasonings tasks.](https://ai.google.dev/gemini-api/docs/models#gemini-2.5-pro)[sparkGemini 2.5 Flash
Our most balanced model, with a 1 million token context window and more.](https://ai.google.dev/gemini-api/docs/models/gemini#gemini-2.5-flash)[sparkGemini 2.5 Flash-Lite
Our fastest and most cost-efficient multimodal model with great performance for high-frequency tasks.](https://ai.google.dev/gemini-api/docs/models/gemini#gemini-2.5-flash-lite)[video_libraryVeo 3.1
Our state-of-the-art video generation model, with native audio.](https://ai.google.dev/gemini-api/docs/video)[sparkGemini 2.5 Pro TTS
Gemini 2.5 model variant with native text-to-speech (TTS) capabilities.](https://ai.google.dev/gemini-api/docs/models/gemini#gemini-2.5-pro-tts)[sparkGemini Robotics-ER 1.5
A vision-language model (VLM) that brings Gemini's agentic capabilities to robotics and enables advanced reasoning in the physical world.](https://ai.google.dev/gemini-api/docs/robotics-overview)

## Explore Capabilities

[imagesmode
Native Image Generation (Nano Banana)
Generate and edit highly contextual images natively with Gemini 2.5 Flash Image.](https://ai.google.dev/gemini-api/docs/image-generation)[article
Long Context
Input millions of tokens to Gemini models and derive understanding from unstructured images, videos, and documents.](https://ai.google.dev/gemini-api/docs/long-context)[code
Structured Outputs
Constrain Gemini to respond with JSON, a structured data format suitable for automated processing.](https://ai.google.dev/gemini-api/docs/structured-output)[functions
Function Calling
Build agentic workflows by connecting Gemini to external APIs and tools.](https://ai.google.dev/gemini-api/docs/function-calling)[videocam
Video Generation with Veo 3.1
Create high-quality video content from text or image prompts with our state-of-the-art model.](https://ai.google.dev/gemini-api/docs/video)[android_recorder
Voice Agents with Live API
Build real-time voice applications and agents with the Live API.](https://ai.google.dev/gemini-api/docs/live)[build
Tools
Connect Gemini to the world through built-in tools like Google Search, URL Context, Google Maps, Code Execution and Computer Use.](https://ai.google.dev/gemini-api/docs/tools)[stacks
Document Understanding
Process up to 1000 pages of PDF files with full multimodal understanding or other text-based file types.](https://ai.google.dev/gemini-api/docs/document-processing)[cognition_2
Thinking
Explore how thinking capabilities improve reasoning for complex tasks and agents.](https://ai.google.dev/gemini-api/docs/thinking)

## Resources

[Google AI Studio
Test prompts, manage your API keys, monitor usage, and build prototypes in our platform for AI builders.
Open Google AI Studio](https://aistudio.google.com)[groupDeveloper Community
Ask questions and find solutions from other developers and Google engineers.
Join the community](https://discuss.ai.google.dev/c/gemini-api/4)[menu_bookAPI Reference
Find detailed information about the Gemini API in the official reference documentation.
Read the API reference](https://ai.google.dev/api)
<br />

<br />

We have updated our[Terms of Service](https://ai.google.dev/gemini-api/terms).  
OUR MOST INTELLIGENT MODEL

## Gemini 3 Pro

The best model in the world for multimodal understanding, and our most powerful agentic and vibe-coding model yet, delivering richer visuals and deeper interactivity, all built on a foundation of state-of-the-art reasoning.

### Expand to learn more

[Try in Google AI Studio](https://aistudio.google.com?model=gemini-3-pro-preview)

#### Model details

### Gemini 3 Pro Preview

|                                    Property                                    |                                                                                                                                                                                            Description                                                                                                                                                                                             |
|--------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| id_cardModel code                                                              | `gemini-3-pro-preview`                                                                                                                                                                                                                                                                                                                                                                             |
| saveSupported data types                                                       | **Inputs** Text, Image, Video, Audio, and PDF **Output** Text                                                                                                                                                                                                                                                                                                                                      |
| token_autoToken limits^[\[\*\]](https://ai.google.dev/gemini-api/docs/tokens)^ | **Input token limit** 1,048,576 **Output token limit** 65,536                                                                                                                                                                                                                                                                                                                                      |
| handymanCapabilities                                                           | **Audio generation** Not supported **Batch API** Supported **Caching** Supported **Code execution** Supported **File search** Supported **Function calling** Supported **Grounding with Google Maps** Not supported **Image generation** Not supported **Live API** Not supported **Search grounding** Supported **Structured outputs** Supported **Thinking** Supported **URL context** Supported |
| 123Versions                                                                    | Read the[model version patterns](https://ai.google.dev/gemini-api/docs/models/gemini#model-versions)for more details. - `Preview: gemini-3-pro-preview`                                                                                                                                                                                                                                            |
| calendar_monthLatest update                                                    | November 2025                                                                                                                                                                                                                                                                                                                                                                                      |
| cognition_2Knowledge cutoff                                                    | January 2025                                                                                                                                                                                                                                                                                                                                                                                       |

### Gemini 3 Pro Image Preview

|                                    Property                                    |                                                                                                                                                                                                    Description                                                                                                                                                                                                     |
|--------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| id_cardModel code                                                              | `gemini-3-pro-image-preview`                                                                                                                                                                                                                                                                                                                                                                                       |
| saveSupported data types                                                       | **Inputs** Image and Text **Output** Image and Text                                                                                                                                                                                                                                                                                                                                                                |
| token_autoToken limits^[\[\*\]](https://ai.google.dev/gemini-api/docs/tokens)^ | **Input token limit** 65,536 **Output token limit** 32,768                                                                                                                                                                                                                                                                                                                                                         |
| handymanCapabilities                                                           | **Audio generation** Not supported **Batch API** Supported **Caching** Not supported **Code execution** Not supported **File search** Not supported **Function calling** Not supported **Grounding with Google Maps** Not supported **Image generation** Supported **Live API** Not supported **Search grounding** Supported **Structured outputs** Supported **Thinking** Supported **URL context** Not supported |
| 123Versions                                                                    | Read the[model version patterns](https://ai.google.dev/gemini-api/docs/models/gemini#model-versions)for more details. - `Preview: gemini-3-pro-image-preview`                                                                                                                                                                                                                                                      |
| calendar_monthLatest update                                                    | November 2025                                                                                                                                                                                                                                                                                                                                                                                                      |
| cognition_2Knowledge cutoff                                                    | January 2025                                                                                                                                                                                                                                                                                                                                                                                                       |

OUR MOST INTELLIGENT MODEL

## Gemini 3 Flash

Our most intelligent model built for speed, combining frontier intelligence with superior search and grounding.

### Expand to learn more

[Try in Google AI Studio](https://aistudio.google.com?model=gemini-3-flash-preview)

#### Model details

### Gemini 3 Flash Preview

|                                    Property                                    |                                                                                                                                                                                            Description                                                                                                                                                                                             |
|--------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| id_cardModel code                                                              | `gemini-3-flash-preview`                                                                                                                                                                                                                                                                                                                                                                           |
| saveSupported data types                                                       | **Inputs** Text, Image, Video, Audio, and PDF **Output** Text                                                                                                                                                                                                                                                                                                                                      |
| token_autoToken limits^[\[\*\]](https://ai.google.dev/gemini-api/docs/tokens)^ | **Input token limit** 1,048,576 **Output token limit** 65,536                                                                                                                                                                                                                                                                                                                                      |
| handymanCapabilities                                                           | **Audio generation** Not supported **Batch API** Supported **Caching** Supported **Code execution** Supported **File search** Supported **Function calling** Supported **Grounding with Google Maps** Not supported **Image generation** Not supported **Live API** Not supported **Search grounding** Supported **Structured outputs** Supported **Thinking** Supported **URL context** Supported |
| 123Versions                                                                    | Read the[model version patterns](https://ai.google.dev/gemini-api/docs/models/gemini#model-versions)for more details. - `Preview: gemini-3-flash-preview`                                                                                                                                                                                                                                          |
| calendar_monthLatest update                                                    | December 2025                                                                                                                                                                                                                                                                                                                                                                                      |
| cognition_2Knowledge cutoff                                                    | January 2025                                                                                                                                                                                                                                                                                                                                                                                       |

FAST AND INTELLIGENT

## Gemini 2.5 Flash

Our best model in terms of price-performance, offering well-rounded capabilities. 2.5 Flash is best for large scale processing, low-latency, high volume tasks that require thinking, and agentic use cases.

### Expand to learn more

[Try in Google AI Studio](https://aistudio.google.com?model=gemini-2.5-flash)

#### Model details

### Gemini 2.5 Flash

|                                    Property                                    |                                                                                                                                                                                          Description                                                                                                                                                                                           |
|--------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| id_cardModel code                                                              | `gemini-2.5-flash`                                                                                                                                                                                                                                                                                                                                                                             |
| saveSupported data types                                                       | **Inputs** Text, images, video, audio **Output** Text                                                                                                                                                                                                                                                                                                                                          |
| token_autoToken limits^[\[\*\]](https://ai.google.dev/gemini-api/docs/tokens)^ | **Input token limit** 1,048,576 **Output token limit** 65,536                                                                                                                                                                                                                                                                                                                                  |
| handymanCapabilities                                                           | **Audio generation** Not supported **Batch API** Supported **Caching** Supported **Code execution** Supported **File search** Supported **Function calling** Supported **Grounding with Google Maps** Supported **Image generation** Not supported **Live API** Not supported **Search grounding** Supported **Structured outputs** Supported **Thinking** Supported **URL context** Supported |
| 123Versions                                                                    | Read the[model version patterns](https://ai.google.dev/gemini-api/docs/models/gemini#model-versions)for more details. - Stable:`gemini-2.5-flash`                                                                                                                                                                                                                                              |
| calendar_monthLatest update                                                    | June 2025                                                                                                                                                                                                                                                                                                                                                                                      |
| cognition_2Knowledge cutoff                                                    | January 2025                                                                                                                                                                                                                                                                                                                                                                                   |

### Gemini 2.5 Flash Preview

|                                    Property                                    |                                                                                                                                                                                            Description                                                                                                                                                                                             |
|--------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| id_cardModel code                                                              | `gemini-2.5-flash-preview-09-2025`                                                                                                                                                                                                                                                                                                                                                                 |
| saveSupported data types                                                       | **Inputs** Text, images, video, audio **Output** Text                                                                                                                                                                                                                                                                                                                                              |
| token_autoToken limits^[\[\*\]](https://ai.google.dev/gemini-api/docs/tokens)^ | **Input token limit** 1,048,576 **Output token limit** 65,536                                                                                                                                                                                                                                                                                                                                      |
| handymanCapabilities                                                           | **Audio generation** Not supported **Batch API** Supported **Caching** Supported **Code execution** Supported **File search** Supported **Function calling** Supported **Grounding with Google Maps** Not supported **Image generation** Not supported **Live API** Not supported **Search grounding** Supported **Structured outputs** Supported **Thinking** Supported **URL Context** Supported |
| 123Versions                                                                    | Read the[model version patterns](https://ai.google.dev/gemini-api/docs/models/gemini#model-versions)for more details. - Preview:`gemini-2.5-flash-preview-09-2025`                                                                                                                                                                                                                                 |
| calendar_monthLatest update                                                    | September 2025                                                                                                                                                                                                                                                                                                                                                                                     |
| cognition_2Knowledge cutoff                                                    | January 2025                                                                                                                                                                                                                                                                                                                                                                                       |

### Gemini 2.5 Flash Image

|                                    Property                                    |                                                                                                                                                                                                      Description                                                                                                                                                                                                       |
|--------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| id_cardModel code                                                              | `gemini-2.5-flash-image`                                                                                                                                                                                                                                                                                                                                                                                               |
| saveSupported data types                                                       | **Inputs** Images and text **Output** Images and text                                                                                                                                                                                                                                                                                                                                                                  |
| token_autoToken limits^[\[\*\]](https://ai.google.dev/gemini-api/docs/tokens)^ | **Input token limit** 65,536 **Output token limit** 32,768                                                                                                                                                                                                                                                                                                                                                             |
| handymanCapabilities                                                           | **Audio generation** Not supported **Batch API** Supported **Caching** Supported **Code execution** Not Supported **File search** Not Supported **Function calling** Not supported **Grounding with Google Maps** Not supported **Image generation** Supported **Live API** Not Supported **Search grounding** Not Supported **Structured outputs** Supported **Thinking** Not Supported **URL context** Not supported |
| 123Versions                                                                    | Read the[model version patterns](https://ai.google.dev/gemini-api/docs/models/gemini#model-versions)for more details. - Stable:`gemini-2.5-flash-image` - Deprecated:`gemini-2.5-flash-image-preview`                                                                                                                                                                                                                  |
| calendar_monthLatest update                                                    | October 2025                                                                                                                                                                                                                                                                                                                                                                                                           |
| cognition_2Knowledge cutoff                                                    | June 2025                                                                                                                                                                                                                                                                                                                                                                                                              |

### Gemini 2.5 Flash Live

|                                    Property                                    |                                                                                                                                                                                                    Description                                                                                                                                                                                                     |
|--------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| id_cardModel code                                                              | `gemini-2.5-flash-native-audio-preview-12-2025`                                                                                                                                                                                                                                                                                                                                                                    |
| saveSupported data types                                                       | **Inputs** Audio, video, text **Output** Audio and text                                                                                                                                                                                                                                                                                                                                                            |
| token_autoToken limits^[\[\*\]](https://ai.google.dev/gemini-api/docs/tokens)^ | **Input token limit** 131,072 **Output token limit** 8,192                                                                                                                                                                                                                                                                                                                                                         |
| handymanCapabilities                                                           | **Audio generation** Supported **Batch API** Not supported **Caching** Not supported **Code execution** Not supported **File search** Not Supported **Function calling** Supported **Grounding with Google Maps** Not supported **Image generation** Not supported **Live API** Supported **Search grounding** Supported **Structured outputs** Not supported **Thinking** Supported **URL context** Not supported |
| 123Versions                                                                    | Read the[model version patterns](https://ai.google.dev/gemini-api/docs/models/gemini#model-versions)for more details. - Preview:`gemini-2.5-flash-native-audio-preview-12-2025` - Preview:`gemini-2.5-flash-native-audio-preview-09-2025`                                                                                                                                                                          |
| calendar_monthLatest update                                                    | September 2025                                                                                                                                                                                                                                                                                                                                                                                                     |
| cognition_2Knowledge cutoff                                                    | January 2025                                                                                                                                                                                                                                                                                                                                                                                                       |

### Gemini 2.5 Flash TTS

|                                    Property                                    |                                                                                                                                                                                                          Description                                                                                                                                                                                                           |
|--------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| id_cardModel code                                                              | `gemini-2.5-flash-preview-tts`                                                                                                                                                                                                                                                                                                                                                                                                 |
| saveSupported data types                                                       | **Inputs** Text **Output** Audio                                                                                                                                                                                                                                                                                                                                                                                               |
| token_autoToken limits^[\[\*\]](https://ai.google.dev/gemini-api/docs/tokens)^ | **Input token limit** 8,192 **Output token limit** 16,384                                                                                                                                                                                                                                                                                                                                                                      |
| handymanCapabilities                                                           | **Audio generation** Supported **Batch API** Supported **Caching** Not supported **Code execution** Not supported **File search** Not Supported **Function calling** Not supported **Grounding with Google Maps** Not supported **Image generation** Not supported **Live API** Not supported **Search grounding** Not supported **Structured outputs** Not supported **Thinking** Not supported **URL context** Not supported |
| 123Versions                                                                    | Read the[model version patterns](https://ai.google.dev/gemini-api/docs/models/gemini#model-versions)for more details. - `gemini-2.5-flash-preview-tts`                                                                                                                                                                                                                                                                         |
| calendar_monthLatest update                                                    | December 2025                                                                                                                                                                                                                                                                                                                                                                                                                  |

ULTRA FAST

## Gemini 2.5 Flash-Lite

Our fastest flash model optimized for cost-efficiency and high throughput.

### Expand to learn more

[Try in Google AI Studio](https://aistudio.google.com?model=gemini-2.5-flash-lite)

#### Model details

### Gemini 2.5 Flash-Lite

|                                    Property                                    |                                                                                                                                                                                          Description                                                                                                                                                                                           |
|--------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| id_cardModel code                                                              | `gemini-2.5-flash-lite`                                                                                                                                                                                                                                                                                                                                                                        |
| saveSupported data types                                                       | **Inputs** Text, image, video, audio, PDF **Output** Text                                                                                                                                                                                                                                                                                                                                      |
| token_autoToken limits^[\[\*\]](https://ai.google.dev/gemini-api/docs/tokens)^ | **Input token limit** 1,048,576 **Output token limit** 65,536                                                                                                                                                                                                                                                                                                                                  |
| handymanCapabilities                                                           | **Audio generation** Not supported **Batch API** Supported **Caching** Supported **Code execution** Supported **File search** Supported **Function calling** Supported **Grounding with Google Maps** Supported **Image generation** Not supported **Live API** Not supported **Search grounding** Supported **Structured outputs** Supported **Thinking** Supported **URL context** Supported |
| 123Versions                                                                    | Read the[model version patterns](https://ai.google.dev/gemini-api/docs/models/gemini#model-versions)for more details. - Stable:`gemini-2.5-flash-lite`                                                                                                                                                                                                                                         |
| calendar_monthLatest update                                                    | July 2025                                                                                                                                                                                                                                                                                                                                                                                      |
| cognition_2Knowledge cutoff                                                    | January 2025                                                                                                                                                                                                                                                                                                                                                                                   |

### Gemini 2.5 Flash-Lite Preview

|                                    Property                                    |                                                                                                                                                                                            Description                                                                                                                                                                                             |
|--------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| id_cardModel code                                                              | `gemini-2.5-flash-lite-preview-09-2025`                                                                                                                                                                                                                                                                                                                                                            |
| saveSupported data types                                                       | **Inputs** Text, image, video, audio, PDF **Output** Text                                                                                                                                                                                                                                                                                                                                          |
| token_autoToken limits^[\[\*\]](https://ai.google.dev/gemini-api/docs/tokens)^ | **Input token limit** 1,048,576 **Output token limit** 65,536                                                                                                                                                                                                                                                                                                                                      |
| handymanCapabilities                                                           | **Audio generation** Not supported **Batch API** Supported **Caching** Supported **Code execution** Supported **File search** Supported **Function calling** Supported **Grounding with Google Maps** Not supported **Image generation** Not supported **Live API** Not supported **Search grounding** Supported **Structured outputs** Supported **Thinking** Supported **URL context** Supported |
| 123Versions                                                                    | Read the[model version patterns](https://ai.google.dev/gemini-api/docs/models/gemini#model-versions)for more details. - Preview:`gemini-2.5-flash-lite-preview-09-2025`                                                                                                                                                                                                                            |
| calendar_monthLatest update                                                    | September 2025                                                                                                                                                                                                                                                                                                                                                                                     |
| cognition_2Knowledge cutoff                                                    | January 2025                                                                                                                                                                                                                                                                                                                                                                                       |

OUR ADVANCED THINKING MODEL

## Gemini 2.5 Pro

Our state-of-the-art thinking model, capable of reasoning over complex problems in code, math, and STEM, as well as analyzing large datasets, codebases, and documents using long context.

### Expand to learn more

[Try in Google AI Studio](https://aistudio.google.com?model=gemini-2.5-pro)

#### Model details

### Gemini 2.5 Pro

|                                    Property                                    |                                                                                                                                                                                          Description                                                                                                                                                                                           |
|--------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| id_cardModel code                                                              | `gemini-2.5-pro`                                                                                                                                                                                                                                                                                                                                                                               |
| saveSupported data types                                                       | **Inputs** Audio, images, video, text, and PDF **Output** Text                                                                                                                                                                                                                                                                                                                                 |
| token_autoToken limits^[\[\*\]](https://ai.google.dev/gemini-api/docs/tokens)^ | **Input token limit** 1,048,576 **Output token limit** 65,536                                                                                                                                                                                                                                                                                                                                  |
| handymanCapabilities                                                           | **Audio generation** Not supported **Batch API** Supported **Caching** Supported **Code execution** Supported **File search** Supported **Function calling** Supported **Grounding with Google Maps** Supported **Image generation** Not supported **Live API** Not supported **Search grounding** Supported **Structured outputs** Supported **Thinking** Supported **URL context** Supported |
| 123Versions                                                                    | Read the[model version patterns](https://ai.google.dev/gemini-api/docs/models/gemini#model-versions)for more details. - `Stable: gemini-2.5-pro`                                                                                                                                                                                                                                               |
| calendar_monthLatest update                                                    | June 2025                                                                                                                                                                                                                                                                                                                                                                                      |
| cognition_2Knowledge cutoff                                                    | January 2025                                                                                                                                                                                                                                                                                                                                                                                   |

### Gemini 2.5 Pro TTS

|                                    Property                                    |                                                                                                                                                                                                          Description                                                                                                                                                                                                           |
|--------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| id_cardModel code                                                              | `gemini-2.5-pro-preview-tts`                                                                                                                                                                                                                                                                                                                                                                                                   |
| saveSupported data types                                                       | **Inputs** Text **Output** Audio                                                                                                                                                                                                                                                                                                                                                                                               |
| token_autoToken limits^[\[\*\]](https://ai.google.dev/gemini-api/docs/tokens)^ | **Input token limit** 8,192 **Output token limit** 16,384                                                                                                                                                                                                                                                                                                                                                                      |
| handymanCapabilities                                                           | **Audio generation** Supported **Batch API** Supported **Caching** Not supported **Code execution** Not supported **File search** Not Supported **Function calling** Not supported **Grounding with Google Maps** Not supported **Image generation** Not supported **Live API** Not supported **Search grounding** Not supported **Structured outputs** Not supported **Thinking** Not supported **URL context** Not supported |
| 123Versions                                                                    | Read the[model version patterns](https://ai.google.dev/gemini-api/docs/models/gemini#model-versions)for more details. - `gemini-2.5-pro-preview-tts`                                                                                                                                                                                                                                                                           |
| calendar_monthLatest update                                                    | December 2025                                                                                                                                                                                                                                                                                                                                                                                                                  |

<br />

## Previous Gemini models

OUR SECOND GENERATION WORKHORSE MODEL

## Gemini 2.0 Flash

Our second generation workhorse model, with a 1 million token context window.

### Expand to learn more

Gemini 2.0 Flash delivers next-gen features and improved capabilities, including superior speed, native tool use, and a 1M token context window.

[Try in Google AI Studio](https://aistudio.google.com?model=gemini-2.0-flash)

#### Model details

### Gemini 2.0 Flash

|                                    Property                                    |                                                                                                                                                                                                Description                                                                                                                                                                                                |
|--------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| id_cardModel code                                                              | `gemini-2.0-flash`                                                                                                                                                                                                                                                                                                                                                                                        |
| saveSupported data types                                                       | **Inputs** Audio, images, video, and text **Output** Text                                                                                                                                                                                                                                                                                                                                                 |
| token_autoToken limits^[\[\*\]](https://ai.google.dev/gemini-api/docs/tokens)^ | **Input token limit** 1,048,576 **Output token limit** 8,192                                                                                                                                                                                                                                                                                                                                              |
| handymanCapabilities                                                           | **Audio generation** Not supported **Batch API** Supported **Caching** Supported **Code execution** Supported **File search** Not supported **Function calling** Supported **Grounding with Google Maps** Supported **Image generation** Not supported **Live API** Not supported **Search grounding** Supported **Structured outputs** Supported **Thinking** Experimental **URL context** Not supported |
| 123Versions                                                                    | Read the[model version patterns](https://ai.google.dev/gemini-api/docs/models/gemini#model-versions)for more details. - Latest:`gemini-2.0-flash` - Stable:`gemini-2.0-flash-001` - Experimental:`gemini-2.0-flash-exp`                                                                                                                                                                                   |
| calendar_monthLatest update                                                    | February 2025                                                                                                                                                                                                                                                                                                                                                                                             |
| cognition_2Knowledge cutoff                                                    | August 2024                                                                                                                                                                                                                                                                                                                                                                                               |

### Gemini 2.0 Flash Image

|                                    Property                                    |                                                                                                                                                                                                      Description                                                                                                                                                                                                       |
|--------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| id_cardModel code                                                              | `gemini-2.0-flash-preview-image-generation`                                                                                                                                                                                                                                                                                                                                                                            |
| saveSupported data types                                                       | **Inputs** Audio, images, video, and text **Output** Text and images                                                                                                                                                                                                                                                                                                                                                   |
| token_autoToken limits^[\[\*\]](https://ai.google.dev/gemini-api/docs/tokens)^ | **Input token limit** 32,768 **Output token limit** 8,192                                                                                                                                                                                                                                                                                                                                                              |
| handymanCapabilities                                                           | **Audio generation** Not supported **Batch API** Supported **Caching** Supported **Code execution** Not Supported **File search** Not supported **Function calling** Not supported **Grounding with Google Maps** Not supported **Image generation** Supported **Live API** Not Supported **Search grounding** Not Supported **Structured outputs** Supported **Thinking** Not Supported **URL context** Not supported |
| 123Versions                                                                    | Read the[model version patterns](https://ai.google.dev/gemini-api/docs/models/gemini#model-versions)for more details. - Preview:`gemini-2.0-flash-preview-image-generation` - gemini-2.0-flash-preview-image-generation is not currently supported in a number of countries in Europe, Middle East \& Africa                                                                                                           |
| calendar_monthLatest update                                                    | May 2025                                                                                                                                                                                                                                                                                                                                                                                                               |
| cognition_2Knowledge cutoff                                                    | August 2024                                                                                                                                                                                                                                                                                                                                                                                                            |

OUR SECOND GENERATION FAST MODEL

## Gemini 2.0 Flash-Lite

Our second generation small workhorse model, with a 1 million token context window.

### Expand to learn more

A Gemini 2.0 Flash model optimized for cost efficiency and low latency.

[Try in Google AI Studio](https://aistudio.google.com?model=gemini-2.0-flash-lite)

#### Model details

|                                    Property                                    |                                                                                                                                                                                                      Description                                                                                                                                                                                                       |
|--------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| id_cardModel code                                                              | `gemini-2.0-flash-lite`                                                                                                                                                                                                                                                                                                                                                                                                |
| saveSupported data types                                                       | **Inputs** Audio, images, video, and text **Output** Text                                                                                                                                                                                                                                                                                                                                                              |
| token_autoToken limits^[\[\*\]](https://ai.google.dev/gemini-api/docs/tokens)^ | **Input token limit** 1,048,576 **Output token limit** 8,192                                                                                                                                                                                                                                                                                                                                                           |
| handymanCapabilities                                                           | **Audio generation** Not supported **Batch API** Supported **Caching** Supported **Code execution** Not supported **File search** Not supported **Function calling** Supported **Grounding with Google Maps** Not supported **Image generation** Not supported **Live API** Not supported **Search grounding** Not supported **Structured outputs** Supported **Thinking** Not Supported **URL context** Not supported |
| 123Versions                                                                    | Read the[model version patterns](https://ai.google.dev/gemini-api/docs/models/gemini#model-versions)for more details. - Latest:`gemini-2.0-flash-lite` - Stable:`gemini-2.0-flash-lite-001`                                                                                                                                                                                                                            |
| calendar_monthLatest update                                                    | February 2025                                                                                                                                                                                                                                                                                                                                                                                                          |
| cognition_2Knowledge cutoff                                                    | August 2024                                                                                                                                                                                                                                                                                                                                                                                                            |

<br />

## Model version name patterns

Gemini models are available in either*stable* ,*preview* ,*latest* , or*experimental*versions.
| **Note:** The following list refers to the model string naming convention as of September, 2025. Models released prior to that may have different naming conventions. Refer to the exact model string if you are using an older model.

### Stable

Points to a specific stable model. Stable models usually don't change. Most production apps should use a specific stable model.

For example:`gemini-2.5-flash`.

### Preview

Points to a preview model which may be used for production. Preview models will typically have billing enabled, might come with more restrictive rate limits and will be deprecated with at least 2 weeks notice.

For example:`gemini-2.5-flash-preview-09-2025`.

### Latest

Points to the latest release for a specific model variation. This can be a stable, preview or experimental release. This alias will get hot-swapped with every new release of a specific model variation. A**2-week notice**will be provided through email before the version behind latest is changed.

For example:`gemini-flash-latest`.

### Experimental

Points to an experimental model which will typically be not be suitable for production use and come with more restrictive rate limits. We release experimental models to gather feedback and get our latest updates into the hands of developers quickly.

Experimental models are not stable and availability of model endpoints is subject to change.

## Model deprecations

For information about model deprecations, visit the[Gemini deprecations](https://ai.google.dev/gemini-api/docs/deprecations)page.
<br />

<br />

| We have updated our[Terms of Service](https://ai.google.dev/gemini-api/terms).

The Gemini API offers text embedding models to generate embeddings for words, phrases, sentences, and code. These foundational embeddings power advanced NLP tasks such as semantic search, classification, and clustering, providing more accurate, context-aware results than keyword-based approaches.

Building Retrieval Augmented Generation (RAG) systems is a common use case for embeddings. Embeddings play a key role in significantly enhancing model outputs with improved factual accuracy, coherence, and contextual richness. They efficiently retrieve relevant information from knowledge bases, represented by embeddings, which are then passed as additional context in the input prompt to language models, guiding it to generate more informed and accurate responses.

To learn more about the available embedding model variants, see the[Model versions](https://ai.google.dev/gemini-api/docs/embeddings#model-versions)section. For higher throughput serving at half the price, try[Batch API Embedding](https://ai.google.dev/gemini-api/docs/embeddings#batch-embedding).

## Generating embeddings

Use the`embedContent`method to generate text embeddings:  

### Python

    from google import genai

    client = genai.Client()

    result = client.models.embed_content(
            model="gemini-embedding-001",
            contents="What is the meaning of life?")

    print(result.embeddings)

### JavaScript

    import { GoogleGenAI } from "@google/genai";

    async function main() {

        const ai = new GoogleGenAI({});

        const response = await ai.models.embedContent({
            model: 'gemini-embedding-001',
            contents: 'What is the meaning of life?',
        });

        console.log(response.embeddings);
    }

    main();

### Go

    package main

    import (
        "context"
        "encoding/json"
        "fmt"
        "log"

        "google.golang.org/genai"
    )

    func main() {
        ctx := context.Background()
        client, err := genai.NewClient(ctx, nil)
        if err != nil {
            log.Fatal(err)
        }

        contents := []*genai.Content{
            genai.NewContentFromText("What is the meaning of life?", genai.RoleUser),
        }
        result, err := client.Models.EmbedContent(ctx,
            "gemini-embedding-001",
            contents,
            nil,
        )
        if err != nil {
            log.Fatal(err)
        }

        embeddings, err := json.MarshalIndent(result.Embeddings, "", "  ")
        if err != nil {
            log.Fatal(err)
        }
        fmt.Println(string(embeddings))
    }

### REST

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent" \
    -H "x-goog-api-key: $GEMINI_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{"model": "models/gemini-embedding-001",
         "content": {"parts":[{"text": "What is the meaning of life?"}]}
        }'

You can also generate embeddings for multiple chunks at once by passing them in as a list of strings.  

### Python

    from google import genai

    client = genai.Client()

    result = client.models.embed_content(
            model="gemini-embedding-001",
            contents= [
                "What is the meaning of life?",
                "What is the purpose of existence?",
                "How do I bake a cake?"
            ])

    for embedding in result.embeddings:
        print(embedding)

### JavaScript

    import { GoogleGenAI } from "@google/genai";

    async function main() {

        const ai = new GoogleGenAI({});

        const response = await ai.models.embedContent({
            model: 'gemini-embedding-001',
            contents: [
                'What is the meaning of life?',
                'What is the purpose of existence?',
                'How do I bake a cake?'
            ],
        });

        console.log(response.embeddings);
    }

    main();

### Go

    package main

    import (
        "context"
        "encoding/json"
        "fmt"
        "log"

        "google.golang.org/genai"
    )

    func main() {
        ctx := context.Background()
        client, err := genai.NewClient(ctx, nil)
        if err != nil {
            log.Fatal(err)
        }

        contents := []*genai.Content{
            genai.NewContentFromText("What is the meaning of life?"),
            genai.NewContentFromText("How does photosynthesis work?"),
            genai.NewContentFromText("Tell me about the history of the internet."),
        }
        result, err := client.Models.EmbedContent(ctx,
            "gemini-embedding-001",
            contents,
            nil,
        )
        if err != nil {
            log.Fatal(err)
        }

        embeddings, err := json.MarshalIndent(result.Embeddings, "", "  ")
        if err != nil {
            log.Fatal(err)
        }
        fmt.Println(string(embeddings))
    }

### REST

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents" \
    -H "x-goog-api-key: $GEMINI_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{"requests": [{
        "model": "models/gemini-embedding-001",
        "content": {
        "parts":[{
            "text": "What is the meaning of life?"}]}, },
        {
        "model": "models/gemini-embedding-001",
        "content": {
        "parts":[{
            "text": "How much wood would a woodchuck chuck?"}]}, },
        {
        "model": "models/gemini-embedding-001",
        "content": {
        "parts":[{
            "text": "How does the brain work?"}]}, }, ]}' 2> /dev/null | grep -C 5 values
        ```

## Specify task type to improve performance

You can use embeddings for a wide range of tasks from classification to document search. Specifying the right task type helps optimize the embeddings for the intended relationships, maximizing accuracy and efficiency. For a complete list of supported task types, see the[Supported task types](https://ai.google.dev/gemini-api/docs/embeddings#supported-task-types)table.

The following example shows how you can use`SEMANTIC_SIMILARITY`to check how similar in meaning strings of texts are.
**Note:** Cosine similarity is a good distance metric because it focuses on direction rather than magnitude, which more accurately reflects conceptual closeness. Values range from -1 (opposite) to 1 (greatest similarity).  

### Python

    from google import genai
    from google.genai import types
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity

    client = genai.Client()

    texts = [
        "What is the meaning of life?",
        "What is the purpose of existence?",
        "How do I bake a cake?"]

    result = [
        np.array(e.values) for e in client.models.embed_content(
            model="gemini-embedding-001",
            contents=texts,
            config=types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY")).embeddings
    ]

    # Calculate cosine similarity. Higher scores = greater semantic similarity.

    embeddings_matrix = np.array(result)
    similarity_matrix = cosine_similarity(embeddings_matrix)

    for i, text1 in enumerate(texts):
        for j in range(i + 1, len(texts)):
            text2 = texts[j]
            similarity = similarity_matrix[i, j]
            print(f"Similarity between '{text1}' and '{text2}': {similarity:.4f}")

### JavaScript

    import { GoogleGenAI } from "@google/genai";
    import * as cosineSimilarity from "compute-cosine-similarity";

    async function main() {
        const ai = new GoogleGenAI({});

        const texts = [
            "What is the meaning of life?",
            "What is the purpose of existence?",
            "How do I bake a cake?",
        ];

        const response = await ai.models.embedContent({
            model: 'gemini-embedding-001',
            contents: texts,
            taskType: 'SEMANTIC_SIMILARITY'
        });

        const embeddings = response.embeddings.map(e => e.values);

        for (let i = 0; i < texts.length; i++) {
            for (let j = i + 1; j < texts.length; j++) {
                const text1 = texts[i];
                const text2 = texts[j];
                const similarity = cosineSimilarity(embeddings[i], embeddings[j]);
                console.log(`Similarity between '${text1}' and '${text2}': ${similarity.toFixed(4)}`);
            }
        }
    }

    main();

### Go

    package main

    import (
        "context"
        "fmt"
        "log"
        "math"

        "google.golang.org/genai"
    )

    // cosineSimilarity calculates the similarity between two vectors.
    func cosineSimilarity(a, b []float32) (float64, error) {
        if len(a) != len(b) {
            return 0, fmt.Errorf("vectors must have the same length")
        }

        var dotProduct, aMagnitude, bMagnitude float64
        for i := 0; i < len(a); i++ {
            dotProduct += float64(a[i] * b[i])
            aMagnitude += float64(a[i] * a[i])
            bMagnitude += float64(b[i] * b[i])
        }

        if aMagnitude == 0 || bMagnitude == 0 {
            return 0, nil
        }

        return dotProduct / (math.Sqrt(aMagnitude) * math.Sqrt(bMagnitude)), nil
    }

    func main() {
        ctx := context.Background()
        client, _ := genai.NewClient(ctx, nil)
        defer client.Close()

        texts := []string{
            "What is the meaning of life?",
            "What is the purpose of existence?",
            "How do I bake a cake?",
        }

        var contents []*genai.Content
        for _, text := range texts {
            contents = append(contents, genai.NewContentFromText(text, genai.RoleUser))
        }

        result, _ := client.Models.EmbedContent(ctx,
            "gemini-embedding-001",
            contents,
            &genai.EmbedContentRequest{TaskType: genai.TaskTypeSemanticSimilarity},
        )

        embeddings := result.Embeddings

        for i := 0; i < len(texts); i++ {
            for j := i + 1; j < len(texts); j++ {
                similarity, _ := cosineSimilarity(embeddings[i].Values, embeddings[j].Values)
                fmt.Printf("Similarity between '%s' and '%s': %.4f\n", texts[i], texts[j], similarity)
            }
        }
    }

### REST

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent" \
    -H "x-goog-api-key: $GEMINI_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{"task_type": "SEMANTIC_SIMILARITY",
        "content": {
        "parts":[{
        "text": "What is the meaning of life?"}, {"text": "How much wood would a woodchuck chuck?"}, {"text": "How does the brain work?"}]}
        }'

The following shows an example output from this code snippet:  

    Similarity between 'What is the meaning of life?' and 'What is the purpose of existence?': 0.9481

    Similarity between 'What is the meaning of life?' and 'How do I bake a cake?': 0.7471

    Similarity between 'What is the purpose of existence?' and 'How do I bake a cake?': 0.7371

### Supported task types

|        Task type         |                                                                                                                  Description                                                                                                                   |                         Examples                          |
|--------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------|
| **SEMANTIC_SIMILARITY**  | Embeddings optimized to assess text similarity.                                                                                                                                                                                                | Recommendation systems, duplicate detection               |
| **CLASSIFICATION**       | Embeddings optimized to classify texts according to preset labels.                                                                                                                                                                             | Sentiment analysis, spam detection                        |
| **CLUSTERING**           | Embeddings optimized to cluster texts based on their similarities.                                                                                                                                                                             | Document organization, market research, anomaly detection |
| **RETRIEVAL_DOCUMENT**   | Embeddings optimized for document search.                                                                                                                                                                                                      | Indexing articles, books, or web pages for search.        |
| **RETRIEVAL_QUERY**      | Embeddings optimized for general search queries. Use`RETRIEVAL_QUERY`for queries;`RETRIEVAL_DOCUMENT`for documents to be retrieved.                                                                                                            | Custom search                                             |
| **CODE_RETRIEVAL_QUERY** | Embeddings optimized for retrieval of code blocks based on natural language queries. Use`CODE_RETRIEVAL_QUERY`for queries;`RETRIEVAL_DOCUMENT`for code blocks to be retrieved.                                                                 | Code suggestions and search                               |
| **QUESTION_ANSWERING**   | Embeddings for questions in a question-answering system, optimized for finding documents that answer the question. Use`QUESTION_ANSWERING`for questions;`RETRIEVAL_DOCUMENT`for documents to be retrieved.                                     | Chatbox                                                   |
| **FACT_VERIFICATION**    | Embeddings for statements that need to be verified, optimized for retrieving documents that contain evidence supporting or refuting the statement. Use`FACT_VERIFICATION`for the target text;`RETRIEVAL_DOCUMENT`for documents to be retrieved | Automated fact-checking systems                           |

## Controlling embedding size

The Gemini embedding model,`gemini-embedding-001`, is trained using the Matryoshka Representation Learning (MRL) technique which teaches a model to learn high-dimensional embeddings that have initial segments (or prefixes) which are also useful, simpler versions of the same data.

Use the`output_dimensionality`parameter to control the size of the output embedding vector. Selecting a smaller output dimensionality can save storage space and increase computational efficiency for downstream applications, while sacrificing little in terms of quality. By default, it outputs a 3072-dimensional embedding, but you can truncate it to a smaller size without losing quality to save storage space. We recommend using 768, 1536, or 3072 output dimensions.  

### Python

    from google import genai
    from google.genai import types

    client = genai.Client()

    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents="What is the meaning of life?",
        config=types.EmbedContentConfig(output_dimensionality=768)
    )

    [embedding_obj] = result.embeddings
    embedding_length = len(embedding_obj.values)

    print(f"Length of embedding: {embedding_length}")

### JavaScript

    import { GoogleGenAI } from "@google/genai";

    async function main() {
        const ai = new GoogleGenAI({});

        const response = await ai.models.embedContent({
            model: 'gemini-embedding-001',
            content: 'What is the meaning of life?',
            outputDimensionality: 768,
        });

        const embeddingLength = response.embedding.values.length;
        console.log(`Length of embedding: ${embeddingLength}`);
    }

    main();

### Go

    package main

    import (
        "context"
        "fmt"
        "log"

        "google.golang.org/genai"
    )

    func main() {
        ctx := context.Background()
        // The client uses Application Default Credentials.
        // Authenticate with 'gcloud auth application-default login'.
        client, err := genai.NewClient(ctx, nil)
        if err != nil {
            log.Fatal(err)
        }
        defer client.Close()

        contents := []*genai.Content{
            genai.NewContentFromText("What is the meaning of life?", genai.RoleUser),
        }

        result, err := client.Models.EmbedContent(ctx,
            "gemini-embedding-001",
            contents,
            &genai.EmbedContentRequest{OutputDimensionality: 768},
        )
        if err != nil {
            log.Fatal(err)
        }

        embedding := result.Embeddings[0]
        embeddingLength := len(embedding.Values)
        fmt.Printf("Length of embedding: %d\n", embeddingLength)
    }

### REST

    curl -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent" \
        -H "x-goog-api-key: $GEMINI_API_KEY" \
        -H 'Content-Type: application/json' \
        -d '{
            "content": {"parts":[{ "text": "What is the meaning of life?"}]},
            "output_dimensionality": 768
        }'

Example output from the code snippet:  

    Length of embedding: 768

## Ensuring quality for smaller dimensions

The 3072 dimension embedding is normalized. Normalized embeddings produce more accurate semantic similarity by comparing vector direction, not magnitude. For other dimensions, including 768 and 1536, you need to normalize the embeddings as follows:  

### Python

    import numpy as np
    from numpy.linalg import norm

    embedding_values_np = np.array(embedding_obj.values)
    normed_embedding = embedding_values_np / np.linalg.norm(embedding_values_np)

    print(f"Normed embedding length: {len(normed_embedding)}")
    print(f"Norm of normed embedding: {np.linalg.norm(normed_embedding):.6f}") # Should be very close to 1

Example output from this code snippet:  

    Normed embedding length: 768
    Norm of normed embedding: 1.000000

The following table shows the MTEB scores, a commonly used benchmark for embeddings, for different dimensions. Notably, the result shows that performance is not strictly tied to the size of the embedding dimension, with lower dimensions achieving scores comparable to their higher dimension counterparts.

| MRL Dimension | MTEB Score |
|---------------|------------|
| 2048          | 68.16      |
| 1536          | 68.17      |
| 768           | 67.99      |
| 512           | 67.55      |
| 256           | 66.19      |
| 128           | 63.31      |

## Use cases

Text embeddings are crucial for a variety of common AI use cases, such as:

- **Retrieval-Augmented Generation (RAG):**Embeddings enhance the quality of generated text by retrieving and incorporating relevant information into the context of a model.
- **Information retrieval:**Search for the most semantically similar text or documents given a piece of input text.

  [Document search tutorialtask](https://github.com/google-gemini/cookbook/blob/main/examples/Talk_to_documents_with_embeddings.ipynb)
- **Search reranking**: Prioritize the most relevant items by semantically scoring initial results against the query.

  [Search reranking tutorialtask](https://github.com/google-gemini/cookbook/blob/main/examples/Search_reranking_using_embeddings.ipynb)
- **Anomaly detection:**Comparing groups of embeddings can help identify hidden trends or outliers.

  [Anomaly detection tutorialbubble_chart](https://github.com/google-gemini/cookbook/blob/main/examples/Anomaly_detection_with_embeddings.ipynb)
- **Classification:**Automatically categorize text based on its content, such as sentiment analysis or spam detection

  [Classification tutorialtoken](https://github.com/google-gemini/cookbook/blob/main/examples/Classify_text_with_embeddings.ipynb)
- **Clustering:**Effectively grasp complex relationships by creating clusters and visualizations of your embeddings.

  [Clustering visualization tutorialbubble_chart](https://github.com/google-gemini/cookbook/blob/main/examples/clustering_with_embeddings.ipynb)

## Storing embeddings

As you take embeddings to production, it is common to use**vector databases** to efficiently store, index, and retrieve high-dimensional embeddings. Google Cloud offers managed data services that can be used for this purpose including[BigQuery](https://cloud.google.com/bigquery/docs/introduction),[AlloyDB](https://cloud.google.com/alloydb/docs/overview), and[Cloud SQL](https://cloud.google.com/sql/docs/postgres/introduction).

The following tutorials show how to use other third party vector databases with Gemini Embedding.

- [ChromaDB tutorialsbolt](https://github.com/google-gemini/cookbook/tree/main/examples/chromadb)
- [Weaviate tutorialsbolt](https://github.com/google-gemini/cookbook/tree/main/examples/weaviate)
- [Pinecone tutorialsbolt](https://github.com/google-gemini/cookbook/blob/main/examples/langchain/Gemini_LangChain_QA_Pinecone_WebLoad.ipynb)

## Model versions

|                                    Property                                    |                                                                                                          Description                                                                                                          |
|--------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| id_cardModel code                                                              | **Gemini API** `gemini-embedding-001`                                                                                                                                                                                         |
| saveSupported data types                                                       | **Input** Text **Output** Text embeddings                                                                                                                                                                                     |
| token_autoToken limits^[\[\*\]](https://ai.google.dev/gemini-api/docs/tokens)^ | **Input token limit** 2,048 **Output dimension size** Flexible, supports: 128 - 3072, Recommended: 768, 1536, 3072                                                                                                            |
| 123Versions                                                                    | Read the[model version patterns](https://ai.google.dev/gemini-api/docs/models/gemini#model-versions)for more details. - Stable:`gemini-embedding-001` - Experimental:`gemini-embedding-exp-03-07`(deprecating in Oct of 2025) |
| calendar_monthLatest update                                                    | June 2025                                                                                                                                                                                                                     |

## Batch embeddings

If latency is not a concern, try using the Gemini Embeddings model with[Batch API](https://ai.google.dev/gemini-api/docs/batch-api#batch-embedding). This allows for much higher throughput at 50% of interactive Embedding pricing. Find examples on how to get started in the[Batch API cookbook](https://github.com/google-gemini/cookbook/blob/main/quickstarts/Batch_mode.ipynb).

## Responsible use notice

Unlike generative AI models that create new content, the Gemini Embedding model is only intended to transform the format of your input data into a numerical representation. While Google is responsible for providing an embedding model that transforms the format of your input data to the numerical-format requested, users retain full responsibility for the data they input and the resulting embeddings. By using the Gemini Embedding model you confirm that you have the necessary rights to any content that you upload. Do not generate content that infringes on others' intellectual property or privacy rights. Your use of this service is subject to our[Prohibited Use Policy](https://policies.google.com/terms/generative-ai/use-policy)and[Google's Terms of Service](https://ai.google.dev/gemini-api/terms).

## Start building with embeddings

Check out the[embeddings quickstart notebook](https://github.com/google-gemini/cookbook/blob/main/quickstarts/Embeddings.ipynb)to explore the model capabilities and learn how to customize and visualize your embeddings.

## Deprecation notice for legacy models

The following models will be deprecated in October, 2025: -`embedding-001`-`embedding-gecko-001`-`gemini-embedding-exp-03-07`(`gemini-embedding-exp`)<br />

Gemini models are built to be multimodal from the ground up, unlocking a wide range of image processing and computer vision tasks including but not limited to image captioning, classification, and visual question answering without having to train specialized ML models.
| **Tip:** In addition to their general multimodal capabilities, Gemini models (2.0 and newer) offer**improved accuracy** for specific use cases like[object detection](https://ai.google.dev/gemini-api/docs/image-understanding#object-detection)and[segmentation](https://ai.google.dev/gemini-api/docs/image-understanding#segmentation), through additional training. See the[Capabilities](https://ai.google.dev/gemini-api/docs/image-understanding#capabilities)section for more details.

## Passing images to Gemini

You can provide images as input to Gemini using two methods:

- [Passing inline image data](https://ai.google.dev/gemini-api/docs/image-understanding#inline-image): Ideal for smaller files (total request size less than 20MB, including prompts).
- [Uploading images using the File API](https://ai.google.dev/gemini-api/docs/image-understanding#upload-image): Recommended for larger files or for reusing images across multiple requests.

### Passing inline image data

You can pass inline image data in the request to`generateContent`. You can provide image data as Base64 encoded strings or by reading local files directly (depending on the language).

The following example shows how to read an image from a local file and pass it to`generateContent`API for processing.  

### Python

      from google import genai
      from google.genai import types

      with open('path/to/small-sample.jpg', 'rb') as f:
          image_bytes = f.read()

      client = genai.Client()
      response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[
          types.Part.from_bytes(
            data=image_bytes,
            mime_type='image/jpeg',
          ),
          'Caption this image.'
        ]
      )

      print(response.text)

### JavaScript

    import { GoogleGenAI } from "@google/genai";
    import * as fs from "node:fs";

    const ai = new GoogleGenAI({});
    const base64ImageFile = fs.readFileSync("path/to/small-sample.jpg", {
      encoding: "base64",
    });

    const contents = [
      {
        inlineData: {
          mimeType: "image/jpeg",
          data: base64ImageFile,
        },
      },
      { text: "Caption this image." },
    ];

    const response = await ai.models.generateContent({
      model: "gemini-2.5-flash",
      contents: contents,
    });
    console.log(response.text);

### Go

    bytes, _ := os.ReadFile("path/to/small-sample.jpg")

    parts := []*genai.Part{
      genai.NewPartFromBytes(bytes, "image/jpeg"),
      genai.NewPartFromText("Caption this image."),
    }

    contents := []*genai.Content{
      genai.NewContentFromParts(parts, genai.RoleUser),
    }

    result, _ := client.Models.GenerateContent(
      ctx,
      "gemini-2.5-flash",
      contents,
      nil,
    )

    fmt.Println(result.Text())

### REST

    IMG_PATH="/path/to/your/image1.jpg"

    if [[ "$(base64 --version 2>&1)" = *"FreeBSD"* ]]; then
    B64FLAGS="--input"
    else
    B64FLAGS="-w0"
    fi

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" \
    -H "x-goog-api-key: $GEMINI_API_KEY" \
    -H 'Content-Type: application/json' \
    -X POST \
    -d '{
        "contents": [{
        "parts":[
            {
                "inline_data": {
                "mime_type":"image/jpeg",
                "data": "'"$(base64 $B64FLAGS $IMG_PATH)"'"
                }
            },
            {"text": "Caption this image."},
        ]
        }]
    }' 2> /dev/null

You can also fetch an image from a URL, convert it to bytes, and pass it to`generateContent`as shown in the following examples.  

### Python

    from google import genai
    from google.genai import types

    import requests

    image_path = "https://goo.gle/instrument-img"
    image_bytes = requests.get(image_path).content
    image = types.Part.from_bytes(
      data=image_bytes, mime_type="image/jpeg"
    )

    client = genai.Client()

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=["What is this image?", image],
    )

    print(response.text)

### JavaScript

    import { GoogleGenAI } from "@google/genai";

    async function main() {
      const ai = new GoogleGenAI({});

      const imageUrl = "https://goo.gle/instrument-img";

      const response = await fetch(imageUrl);
      const imageArrayBuffer = await response.arrayBuffer();
      const base64ImageData = Buffer.from(imageArrayBuffer).toString('base64');

      const result = await ai.models.generateContent({
        model: "gemini-2.5-flash",
        contents: [
        {
          inlineData: {
            mimeType: 'image/jpeg',
            data: base64ImageData,
          },
        },
        { text: "Caption this image." }
      ],
      });
      console.log(result.text);
    }

    main();

### Go

    package main

    import (
      "context"
      "fmt"
      "os"
      "io"
      "net/http"
      "google.golang.org/genai"
    )

    func main() {
      ctx := context.Background()
      client, err := genai.NewClient(ctx, nil)
      if err != nil {
          log.Fatal(err)
      }

      // Download the image.
      imageResp, _ := http.Get("https://goo.gle/instrument-img")

      imageBytes, _ := io.ReadAll(imageResp.Body)

      parts := []*genai.Part{
        genai.NewPartFromBytes(imageBytes, "image/jpeg"),
        genai.NewPartFromText("Caption this image."),
      }

      contents := []*genai.Content{
        genai.NewContentFromParts(parts, genai.RoleUser),
      }

      result, _ := client.Models.GenerateContent(
        ctx,
        "gemini-2.5-flash",
        contents,
        nil,
      )

      fmt.Println(result.Text())
    }

### REST

    IMG_URL="https://goo.gle/instrument-img"

    MIME_TYPE=$(curl -sIL "$IMG_URL" | grep -i '^content-type:' | awk -F ': ' '{print $2}' | sed 's/\r$//' | head -n 1)
    if [[ -z "$MIME_TYPE" || ! "$MIME_TYPE" == image/* ]]; then
      MIME_TYPE="image/jpeg"
    fi

    # Check for macOS
    if [[ "$(uname)" == "Darwin" ]]; then
      IMAGE_B64=$(curl -sL "$IMG_URL" | base64 -b 0)
    elif [[ "$(base64 --version 2>&1)" = *"FreeBSD"* ]]; then
      IMAGE_B64=$(curl -sL "$IMG_URL" | base64)
    else
      IMAGE_B64=$(curl -sL "$IMG_URL" | base64 -w0)
    fi

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" \
        -H "x-goog-api-key: $GEMINI_API_KEY" \
        -H 'Content-Type: application/json' \
        -X POST \
        -d '{
          "contents": [{
            "parts":[
                {
                  "inline_data": {
                    "mime_type":"'"$MIME_TYPE"'",
                    "data": "'"$IMAGE_B64"'"
                  }
                },
                {"text": "Caption this image."}
            ]
          }]
        }' 2> /dev/null

| **Note:** Inline image data limits your total request size (text prompts, system instructions, and inline bytes) to 20MB. For larger requests,[upload image files](https://ai.google.dev/gemini-api/docs/image-understanding#upload-image)using the File API. Files API is also more efficient for scenarios that use the same image repeatedly.

### Uploading images using the File API

For large files or to be able to use the same image file repeatedly, use the Files API. The following code uploads an image file and then uses the file in a call to`generateContent`. See the[Files API guide](https://ai.google.dev/gemini-api/docs/files)for more information and examples.  

### Python

    from google import genai

    client = genai.Client()

    my_file = client.files.upload(file="path/to/sample.jpg")

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[my_file, "Caption this image."],
    )

    print(response.text)

### JavaScript

    import {
      GoogleGenAI,
      createUserContent,
      createPartFromUri,
    } from "@google/genai";

    const ai = new GoogleGenAI({});

    async function main() {
      const myfile = await ai.files.upload({
        file: "path/to/sample.jpg",
        config: { mimeType: "image/jpeg" },
      });

      const response = await ai.models.generateContent({
        model: "gemini-2.5-flash",
        contents: createUserContent([
          createPartFromUri(myfile.uri, myfile.mimeType),
          "Caption this image.",
        ]),
      });
      console.log(response.text);
    }

    await main();

### Go

    package main

    import (
      "context"
      "fmt"
      "os"
      "google.golang.org/genai"
    )

    func main() {
      ctx := context.Background()
      client, err := genai.NewClient(ctx, nil)
      if err != nil {
          log.Fatal(err)
      }

      uploadedFile, _ := client.Files.UploadFromPath(ctx, "path/to/sample.jpg", nil)

      parts := []*genai.Part{
          genai.NewPartFromText("Caption this image."),
          genai.NewPartFromURI(uploadedFile.URI, uploadedFile.MIMEType),
      }

      contents := []*genai.Content{
          genai.NewContentFromParts(parts, genai.RoleUser),
      }

      result, _ := client.Models.GenerateContent(
          ctx,
          "gemini-2.5-flash",
          contents,
          nil,
      )

      fmt.Println(result.Text())
    }

### REST

    IMAGE_PATH="path/to/sample.jpg"
    MIME_TYPE=$(file -b --mime-type "${IMAGE_PATH}")
    NUM_BYTES=$(wc -c < "${IMAGE_PATH}")
    DISPLAY_NAME=IMAGE

    tmp_header_file=upload-header.tmp

    # Initial resumable request defining metadata.
    # The upload url is in the response headers dump them to a file.
    curl "https://generativelanguage.googleapis.com/upload/v1beta/files" \
      -H "x-goog-api-key: $GEMINI_API_KEY" \
      -D upload-header.tmp \
      -H "X-Goog-Upload-Protocol: resumable" \
      -H "X-Goog-Upload-Command: start" \
      -H "X-Goog-Upload-Header-Content-Length: ${NUM_BYTES}" \
      -H "X-Goog-Upload-Header-Content-Type: ${MIME_TYPE}" \
      -H "Content-Type: application/json" \
      -d "{'file': {'display_name': '${DISPLAY_NAME}'}}" 2> /dev/null

    upload_url=$(grep -i "x-goog-upload-url: " "${tmp_header_file}" | cut -d" " -f2 | tr -d "\r")
    rm "${tmp_header_file}"

    # Upload the actual bytes.
    curl "${upload_url}" \
      -H "x-goog-api-key: $GEMINI_API_KEY" \
      -H "Content-Length: ${NUM_BYTES}" \
      -H "X-Goog-Upload-Offset: 0" \
      -H "X-Goog-Upload-Command: upload, finalize" \
      --data-binary "@${IMAGE_PATH}" 2> /dev/null > file_info.json

    file_uri=$(jq -r ".file.uri" file_info.json)
    echo file_uri=$file_uri

    # Now generate content using that file
    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" \
        -H "x-goog-api-key: $GEMINI_API_KEY" \
        -H 'Content-Type: application/json' \
        -X POST \
        -d '{
          "contents": [{
            "parts":[
              {"file_data":{"mime_type": "'"${MIME_TYPE}"'", "file_uri": "'"${file_uri}"'"}},
              {"text": "Caption this image."}]
            }]
          }' 2> /dev/null > response.json

    cat response.json
    echo

    jq ".candidates[].content.parts[].text" response.json

## Prompting with multiple images

You can provide multiple images in a single prompt by including multiple image`Part`objects in the`contents`array. These can be a mix of inline data (local files or URLs) and File API references.  

### Python

    from google import genai
    from google.genai import types

    client = genai.Client()

    # Upload the first image
    image1_path = "path/to/image1.jpg"
    uploaded_file = client.files.upload(file=image1_path)

    # Prepare the second image as inline data
    image2_path = "path/to/image2.png"
    with open(image2_path, 'rb') as f:
        img2_bytes = f.read()

    # Create the prompt with text and multiple images
    response = client.models.generate_content(

        model="gemini-2.5-flash",
        contents=[
            "What is different between these two images?",
            uploaded_file,  # Use the uploaded file reference
            types.Part.from_bytes(
                data=img2_bytes,
                mime_type='image/png'
            )
        ]
    )

    print(response.text)

### JavaScript

    import {
      GoogleGenAI,
      createUserContent,
      createPartFromUri,
    } from "@google/genai";
    import * as fs from "node:fs";

    const ai = new GoogleGenAI({});

    async function main() {
      // Upload the first image
      const image1_path = "path/to/image1.jpg";
      const uploadedFile = await ai.files.upload({
        file: image1_path,
        config: { mimeType: "image/jpeg" },
      });

      // Prepare the second image as inline data
      const image2_path = "path/to/image2.png";
      const base64Image2File = fs.readFileSync(image2_path, {
        encoding: "base64",
      });

      // Create the prompt with text and multiple images

      const response = await ai.models.generateContent({

        model: "gemini-2.5-flash",
        contents: createUserContent([
          "What is different between these two images?",
          createPartFromUri(uploadedFile.uri, uploadedFile.mimeType),
          {
            inlineData: {
              mimeType: "image/png",
              data: base64Image2File,
            },
          },
        ]),
      });
      console.log(response.text);
    }

    await main();

### Go

    // Upload the first image
    image1Path := "path/to/image1.jpg"
    uploadedFile, _ := client.Files.UploadFromPath(ctx, image1Path, nil)

    // Prepare the second image as inline data
    image2Path := "path/to/image2.jpeg"
    imgBytes, _ := os.ReadFile(image2Path)

    parts := []*genai.Part{
      genai.NewPartFromText("What is different between these two images?"),
      genai.NewPartFromBytes(imgBytes, "image/jpeg"),
      genai.NewPartFromURI(uploadedFile.URI, uploadedFile.MIMEType),
    }

    contents := []*genai.Content{
      genai.NewContentFromParts(parts, genai.RoleUser),
    }

    result, _ := client.Models.GenerateContent(
      ctx,
      "gemini-2.5-flash",
      contents,
      nil,
    )

    fmt.Println(result.Text())

### REST

    # Upload the first image
    IMAGE1_PATH="path/to/image1.jpg"
    MIME1_TYPE=$(file -b --mime-type "${IMAGE1_PATH}")
    NUM1_BYTES=$(wc -c < "${IMAGE1_PATH}")
    DISPLAY_NAME1=IMAGE1

    tmp_header_file1=upload-header1.tmp

    curl "https://generativelanguage.googleapis.com/upload/v1beta/files" \
      -H "x-goog-api-key: $GEMINI_API_KEY" \
      -D upload-header1.tmp \
      -H "X-Goog-Upload-Protocol: resumable" \
      -H "X-Goog-Upload-Command: start" \
      -H "X-Goog-Upload-Header-Content-Length: ${NUM1_BYTES}" \
      -H "X-Goog-Upload-Header-Content-Type: ${MIME1_TYPE}" \
      -H "Content-Type: application/json" \
      -d "{'file': {'display_name': '${DISPLAY_NAME1}'}}" 2> /dev/null

    upload_url1=$(grep -i "x-goog-upload-url: " "${tmp_header_file1}" | cut -d" " -f2 | tr -d "\r")
    rm "${tmp_header_file1}"

    curl "${upload_url1}" \
      -H "Content-Length: ${NUM1_BYTES}" \
      -H "X-Goog-Upload-Offset: 0" \
      -H "X-Goog-Upload-Command: upload, finalize" \
      --data-binary "@${IMAGE1_PATH}" 2> /dev/null > file_info1.json

    file1_uri=$(jq ".file.uri" file_info1.json)
    echo file1_uri=$file1_uri

    # Prepare the second image (inline)
    IMAGE2_PATH="path/to/image2.png"
    MIME2_TYPE=$(file -b --mime-type "${IMAGE2_PATH}")

    if [[ "$(base64 --version 2>&1)" = *"FreeBSD"* ]]; then
      B64FLAGS="--input"
    else
      B64FLAGS="-w0"
    fi
    IMAGE2_BASE64=$(base64 $B64FLAGS $IMAGE2_PATH)

    # Now generate content using both images
    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" \
        -H "x-goog-api-key: $GEMINI_API_KEY" \
        -H 'Content-Type: application/json' \
        -X POST \
        -d '{
          "contents": [{
            "parts":[
              {"text": "What is different between these two images?"},
              {"file_data":{"mime_type": "'"${MIME1_TYPE}"'", "file_uri": '$file1_uri'}},
              {
                "inline_data": {
                  "mime_type":"'"${MIME2_TYPE}"'",
                  "data": "'"$IMAGE2_BASE64"'"
                }
              }
            ]
          }]
        }' 2> /dev/null > response.json

    cat response.json
    echo

    jq ".candidates[].content.parts[].text" response.json

## Object detection

From Gemini 2.0 onwards, models are further trained to detect objects in an image and get their bounding box coordinates. The coordinates, relative to image dimensions, scale to \[0, 1000\]. You need to descale these coordinates based on your original image size.  

### Python

    from google import genai
    from google.genai import types
    from PIL import Image
    import json

    client = genai.Client()
    prompt = "Detect the all of the prominent items in the image. The box_2d should be [ymin, xmin, ymax, xmax] normalized to 0-1000."

    image = Image.open("/path/to/image.png")

    config = types.GenerateContentConfig(
      response_mime_type="application/json"
      )

    response = client.models.generate_content(model="gemini-2.5-flash",
                                              contents=[image, prompt],
                                              config=config
                                              )

    width, height = image.size
    bounding_boxes = json.loads(response.text)

    converted_bounding_boxes = []
    for bounding_box in bounding_boxes:
        abs_y1 = int(bounding_box["box_2d"][0]/1000 * height)
        abs_x1 = int(bounding_box["box_2d"][1]/1000 * width)
        abs_y2 = int(bounding_box["box_2d"][2]/1000 * height)
        abs_x2 = int(bounding_box["box_2d"][3]/1000 * width)
        converted_bounding_boxes.append([abs_x1, abs_y1, abs_x2, abs_y2])

    print("Image size: ", width, height)
    print("Bounding boxes:", converted_bounding_boxes)

| **Note:** The model also supports generating bounding boxes based on custom instructions, such as: "Show bounding boxes of all green objects in this image". It also support custom labels like "label the items with the allergens they can contain".

For more examples, check following notebooks in the[Gemini Cookbook](https://github.com/google-gemini/cookbook):

- [2D spatial understanding notebook](https://colab.research.google.com/github/google-gemini/cookbook/blob/main/quickstarts/Spatial_understanding.ipynb)
- [Experimental 3D pointing notebook](https://colab.research.google.com/github/google-gemini/cookbook/blob/main/examples/Spatial_understanding_3d.ipynb)

## Segmentation

Starting with Gemini 2.5, models not only detect items but also segment them and provide their contour masks.

The model predicts a JSON list, where each item represents a segmentation mask. Each item has a bounding box ("`box_2d`") in the format`[y0, x0, y1, x1]`with normalized coordinates between 0 and 1000, a label ("`label`") that identifies the object, and finally the segmentation mask inside the bounding box, as base64 encoded png that is a probability map with values between 0 and 255. The mask needs to be resized to match the bounding box dimensions, then binarized at your confidence threshold (127 for the midpoint).
**Note:** For better results, disable[thinking](https://ai.google.dev/gemini-api/docs/thinking)by setting the thinking budget to 0. See code sample below for an example.  

### Python

    from google import genai
    from google.genai import types
    from PIL import Image, ImageDraw
    import io
    import base64
    import json
    import numpy as np
    import os

    client = genai.Client()

    def parse_json(json_output: str):
      # Parsing out the markdown fencing
      lines = json_output.splitlines()
      for i, line in enumerate(lines):
        if line == "```json":
          json_output = "\n".join(lines[i+1:])  # Remove everything before "```json"
          output = json_output.split("```")[0]  # Remove everything after the closing "```"
          break  # Exit the loop once "```json" is found
      return json_output

    def extract_segmentation_masks(image_path: str, output_dir: str = "segmentation_outputs"):
      # Load and resize image
      im = Image.open(image_path)
      im.thumbnail([1024, 1024], Image.Resampling.LANCZOS)

      prompt = """
      Give the segmentation masks for the wooden and glass items.
      Output a JSON list of segmentation masks where each entry contains the 2D
      bounding box in the key "box_2d", the segmentation mask in key "mask", and
      the text label in the key "label". Use descriptive labels.
      """

      config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0) # set thinking_budget to 0 for better results in object detection
      )

      response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt, im], # Pillow images can be directly passed as inputs (which will be converted by the SDK)
        config=config
      )

      # Parse JSON response
      items = json.loads(parse_json(response.text))

      # Create output directory
      os.makedirs(output_dir, exist_ok=True)

      # Process each mask
      for i, item in enumerate(items):
          # Get bounding box coordinates
          box = item["box_2d"]
          y0 = int(box[0] / 1000 * im.size[1])
          x0 = int(box[1] / 1000 * im.size[0])
          y1 = int(box[2] / 1000 * im.size[1])
          x1 = int(box[3] / 1000 * im.size[0])

          # Skip invalid boxes
          if y0 >= y1 or x0 >= x1:
              continue

          # Process mask
          png_str = item["mask"]
          if not png_str.startswith("data:image/png;base64,"):
              continue

          # Remove prefix
          png_str = png_str.removeprefix("data:image/png;base64,")
          mask_data = base64.b64decode(png_str)
          mask = Image.open(io.BytesIO(mask_data))

          # Resize mask to match bounding box
          mask = mask.resize((x1 - x0, y1 - y0), Image.Resampling.BILINEAR)

          # Convert mask to numpy array for processing
          mask_array = np.array(mask)

          # Create overlay for this mask
          overlay = Image.new('RGBA', im.size, (0, 0, 0, 0))
          overlay_draw = ImageDraw.Draw(overlay)

          # Create overlay for the mask
          color = (255, 255, 255, 200)
          for y in range(y0, y1):
              for x in range(x0, x1):
                  if mask_array[y - y0, x - x0] > 128:  # Threshold for mask
                      overlay_draw.point((x, y), fill=color)

          # Save individual mask and its overlay
          mask_filename = f"{item['label']}_{i}_mask.png"
          overlay_filename = f"{item['label']}_{i}_overlay.png"

          mask.save(os.path.join(output_dir, mask_filename))

          # Create and save overlay
          composite = Image.alpha_composite(im.convert('RGBA'), overlay)
          composite.save(os.path.join(output_dir, overlay_filename))
          print(f"Saved mask and overlay for {item['label']} to {output_dir}")

    # Example usage
    if __name__ == "__main__":
      extract_segmentation_masks("path/to/image.png")

Check the[segmentation example](https://colab.research.google.com/github/google-gemini/cookbook/blob/main/quickstarts/Spatial_understanding.ipynb#scrollTo=WQJTJ8wdGOKx)in the cookbook guide for a more detailed example.
![A table with cupcakes, with the wooden and glass objects highlighted](https://ai.google.dev/static/gemini-api/docs/images/segmentation.jpg)An example segmentation output with objects and segmentation masks

## Supported image formats

Gemini supports the following image format MIME types:

- PNG -`image/png`
- JPEG -`image/jpeg`
- WEBP -`image/webp`
- HEIC -`image/heic`
- HEIF -`image/heif`

## Capabilities

All Gemini model versions are multimodal and can be utilized in a wide range of image processing and computer vision tasks including but not limited to image captioning, visual question and answering, image classification, object detection and segmentation.

Gemini can reduce the need to use specialized ML models depending on your quality and performance requirements.

Some later model versions are specifically trained improve accuracy of specialized tasks in addition to generic capabilities:

- **Gemini 2.0 models** are further trained to support enhanced[object detection](https://ai.google.dev/gemini-api/docs/image-understanding#object-detection).

- **Gemini 2.5 models** are further trained to support enhanced[segmentation](https://ai.google.dev/gemini-api/docs/image-understanding#segmentation)in addition to[object detection](https://ai.google.dev/gemini-api/docs/image-understanding#object-detection).

## Limitations and key technical information

### File limit

Gemini 2.5 Pro/Flash, 2.0 Flash, 1.5 Pro, and 1.5 Flash support a maximum of 3,600 image files per request.

### Token calculation

- **Gemini 1.5 Flash and Gemini 1.5 Pro**: 258 tokens if both dimensions \<= 384 pixels. Larger images are tiled (min tile 256px, max 768px, resized to 768x768), with each tile costing 258 tokens.
- **Gemini 2.0 Flash and Gemini 2.5 Flash/Pro**: 258 tokens if both dimensions \<= 384 pixels. Larger images are tiled into 768x768 pixel tiles, each costing 258 tokens.

A rough formula for calculating the number of tiles is as follows:

- Calculate the crop unit size which is roughly: floor(min(width, height) / 1.5).
- Divide each dimension by the crop unit size and multiply together to get the number of tiles.

For example, for an image of dimensions 960x540 would have a crop unit size of 360. Divide each dimension by 360 and the number of tile is 3 \* 2 = 6.

### Media resolution

Gemini 3 introduces granular control over multimodal vision processing with the`media_resolution`parameter. The`media_resolution`parameter determines the**maximum number of tokens allocated per input image or video frame.**Higher resolutions improve the model's ability to read fine text or identify small details, but increase token usage and latency.

For more details about the parameter and how it can impact token calculations, see the[media resolution](https://ai.google.dev/gemini-api/docs/media-resolution)guide.

## Tips and best practices

- Verify that images are correctly rotated.
- Use clear, non-blurry images.
- When using a single image with text, place the text prompt*after* the image part in the`contents`array.

## What's next

This guide shows you how to upload image files and generate text outputs from image inputs. To learn more, see the following resources:

- [Files API](https://ai.google.dev/gemini-api/docs/files): Learn more about uploading and managing files for use with Gemini.
- [System instructions](https://ai.google.dev/gemini-api/docs/text-generation#system-instructions): System instructions let you steer the behavior of the model based on your specific needs and use cases.
- [File prompting strategies](https://ai.google.dev/gemini-api/docs/files#prompt-guide): The Gemini API supports prompting with text, image, audio, and video data, also known as multimodal prompting.
- [Safety guidance](https://ai.google.dev/gemini-api/docs/safety-guidance): Sometimes generative AI models produce unexpected outputs, such as outputs that are inaccurate, biased, or offensive. Post-processing and human evaluation are essential to limit the risk of harm from such outputs.
<br />

Gemini models can process documents in PDF format, using native vision to understand entire document contexts. This goes beyond just text extraction, allowing Gemini to:

- Analyze and interpret content, including text, images, diagrams, charts, and tables, even in long documents up to 1000 pages.
- Extract information into[structured output](https://ai.google.dev/gemini-api/docs/structured-output)formats.
- Summarize and answer questions based on both the visual and textual elements in a document.
- Transcribe document content (e.g. to HTML), preserving layouts and formatting, for use in downstream applications.

You can also pass non-PDF documents in the same way but Gemini will see them as normal text which will eliminate context like charts or formatting.

## Passing PDF data inline

You can pass PDF data inline in the request to`generateContent`. This is best suited for smaller documents or temporary processing where you don't need to reference the file in subsequent requests. We recommend using the[Files API](https://ai.google.dev/gemini-api/docs/document-processing#large-pdfs)for larger documents that you need to refer to in multi-turn interactions to improve request latency and reduce bandwidth usage.

The following example shows you how to fetch a PDF from a URL and convert it to bytes for processing:  

### Python

    from google import genai
    from google.genai import types
    import httpx

    client = genai.Client()

    doc_url = "https://discovery.ucl.ac.uk/id/eprint/10089234/1/343019_3_art_0_py4t4l_convrt.pdf"

    # Retrieve and encode the PDF byte
    doc_data = httpx.get(doc_url).content

    prompt = "Summarize this document"
    response = client.models.generate_content(
      model="gemini-2.5-flash",
      contents=[
          types.Part.from_bytes(
            data=doc_data,
            mime_type='application/pdf',
          ),
          prompt])
    print(response.text)

### JavaScript

    import { GoogleGenAI } from "@google/genai";

    const ai = new GoogleGenAI({ apiKey: "GEMINI_API_KEY" });

    async function main() {
        const pdfResp = await fetch('https://discovery.ucl.ac.uk/id/eprint/10089234/1/343019_3_art_0_py4t4l_convrt.pdf')
            .then((response) => response.arrayBuffer());

        const contents = [
            { text: "Summarize this document" },
            {
                inlineData: {
                    mimeType: 'application/pdf',
                    data: Buffer.from(pdfResp).toString("base64")
                }
            }
        ];

        const response = await ai.models.generateContent({
            model: "gemini-2.5-flash",
            contents: contents
        });
        console.log(response.text);
    }

    main();

### Go

    package main

    import (
        "context"
        "fmt"
        "io"
        "net/http"
        "os"
        "google.golang.org/genai"
    )

    func main() {

        ctx := context.Background()
        client, _ := genai.NewClient(ctx, &genai.ClientConfig{
            APIKey:  os.Getenv("GEMINI_API_KEY"),
            Backend: genai.BackendGeminiAPI,
        })

        pdfResp, _ := http.Get("https://discovery.ucl.ac.uk/id/eprint/10089234/1/343019_3_art_0_py4t4l_convrt.pdf")
        var pdfBytes []byte
        if pdfResp != nil && pdfResp.Body != nil {
            pdfBytes, _ = io.ReadAll(pdfResp.Body)
            pdfResp.Body.Close()
        }

        parts := []*genai.Part{
            &genai.Part{
                InlineData: &genai.Blob{
                    MIMEType: "application/pdf",
                    Data:     pdfBytes,
                },
            },
            genai.NewPartFromText("Summarize this document"),
        }

        contents := []*genai.Content{
            genai.NewContentFromParts(parts, genai.RoleUser),
        }

        result, _ := client.Models.GenerateContent(
            ctx,
            "gemini-2.5-flash",
            contents,
            nil,
        )

        fmt.Println(result.Text())
    }

### REST

    DOC_URL="https://discovery.ucl.ac.uk/id/eprint/10089234/1/343019_3_art_0_py4t4l_convrt.pdf"
    PROMPT="Summarize this document"
    DISPLAY_NAME="base64_pdf"

    # Download the PDF
    wget -O "${DISPLAY_NAME}.pdf" "${DOC_URL}"

    # Check for FreeBSD base64 and set flags accordingly
    if [[ "$(base64 --version 2>&1)" = *"FreeBSD"* ]]; then
      B64FLAGS="--input"
    else
      B64FLAGS="-w0"
    fi

    # Base64 encode the PDF
    ENCODED_PDF=$(base64 $B64FLAGS "${DISPLAY_NAME}.pdf")

    # Generate content using the base64 encoded PDF
    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=$GOOGLE_API_KEY" \
        -H 'Content-Type: application/json' \
        -X POST \
        -d '{
          "contents": [{
            "parts":[
              {"inline_data": {"mime_type": "application/pdf", "data": "'"$ENCODED_PDF"'"}},
              {"text": "'$PROMPT'"}
            ]
          }]
        }' 2> /dev/null > response.json

    cat response.json
    echo

    jq ".candidates[].content.parts[].text" response.json

    # Clean up the downloaded PDF
    rm "${DISPLAY_NAME}.pdf"

You can also read a PDF from a local file for processing:  

### Python

    from google import genai
    from google.genai import types
    import pathlib

    client = genai.Client()

    # Retrieve and encode the PDF byte
    filepath = pathlib.Path('file.pdf')

    prompt = "Summarize this document"
    response = client.models.generate_content(
      model="gemini-2.5-flash",
      contents=[
          types.Part.from_bytes(
            data=filepath.read_bytes(),
            mime_type='application/pdf',
          ),
          prompt])
    print(response.text)

### JavaScript

    import { GoogleGenAI } from "@google/genai";
    import * as fs from 'fs';

    const ai = new GoogleGenAI({ apiKey: "GEMINI_API_KEY" });

    async function main() {
        const contents = [
            { text: "Summarize this document" },
            {
                inlineData: {
                    mimeType: 'application/pdf',
                    data: Buffer.from(fs.readFileSync("content/343019_3_art_0_py4t4l_convrt.pdf")).toString("base64")
                }
            }
        ];

        const response = await ai.models.generateContent({
            model: "gemini-2.5-flash",
            contents: contents
        });
        console.log(response.text);
    }

    main();

### Go

    package main

    import (
        "context"
        "fmt"
        "os"
        "google.golang.org/genai"
    )

    func main() {

        ctx := context.Background()
        client, _ := genai.NewClient(ctx, &genai.ClientConfig{
            APIKey:  os.Getenv("GEMINI_API_KEY"),
            Backend: genai.BackendGeminiAPI,
        })

        pdfBytes, _ := os.ReadFile("path/to/your/file.pdf")

        parts := []*genai.Part{
            &genai.Part{
                InlineData: &genai.Blob{
                    MIMEType: "application/pdf",
                    Data:     pdfBytes,
                },
            },
            genai.NewPartFromText("Summarize this document"),
        }
        contents := []*genai.Content{
            genai.NewContentFromParts(parts, genai.RoleUser),
        }

        result, _ := client.Models.GenerateContent(
            ctx,
            "gemini-2.5-flash",
            contents,
            nil,
        )

        fmt.Println(result.Text())
    }

## Uploading PDFs using the Files API

We recommend you use Files API for larger files or when you intend to reuse a document across multiple requests. This improves request latency and reduces bandwidth usage by decoupling the file upload from the model requests.
| **Note:** The Files API is available at no cost in all regions where the Gemini API is available. Uploaded files are stored for 48 hours.

### Large PDFs from URLs

Use the File API to simplify uploading and processing large PDF files from URLs:  

### Python

    from google import genai
    from google.genai import types
    import io
    import httpx

    client = genai.Client()

    long_context_pdf_path = "https://www.nasa.gov/wp-content/uploads/static/history/alsj/a17/A17_FlightPlan.pdf"

    # Retrieve and upload the PDF using the File API
    doc_io = io.BytesIO(httpx.get(long_context_pdf_path).content)

    sample_doc = client.files.upload(
      # You can pass a path or a file-like object here
      file=doc_io,
      config=dict(
        mime_type='application/pdf')
    )

    prompt = "Summarize this document"

    response = client.models.generate_content(
      model="gemini-2.5-flash",
      contents=[sample_doc, prompt])
    print(response.text)

### JavaScript

    import { createPartFromUri, GoogleGenAI } from "@google/genai";

    const ai = new GoogleGenAI({ apiKey: "GEMINI_API_KEY" });

    async function main() {

        const pdfBuffer = await fetch("https://www.nasa.gov/wp-content/uploads/static/history/alsj/a17/A17_FlightPlan.pdf")
            .then((response) => response.arrayBuffer());

        const fileBlob = new Blob([pdfBuffer], { type: 'application/pdf' });

        const file = await ai.files.upload({
            file: fileBlob,
            config: {
                displayName: 'A17_FlightPlan.pdf',
            },
        });

        // Wait for the file to be processed.
        let getFile = await ai.files.get({ name: file.name });
        while (getFile.state === 'PROCESSING') {
            getFile = await ai.files.get({ name: file.name });
            console.log(`current file status: ${getFile.state}`);
            console.log('File is still processing, retrying in 5 seconds');

            await new Promise((resolve) => {
                setTimeout(resolve, 5000);
            });
        }
        if (file.state === 'FAILED') {
            throw new Error('File processing failed.');
        }

        // Add the file to the contents.
        const content = [
            'Summarize this document',
        ];

        if (file.uri && file.mimeType) {
            const fileContent = createPartFromUri(file.uri, file.mimeType);
            content.push(fileContent);
        }

        const response = await ai.models.generateContent({
            model: 'gemini-2.5-flash',
            contents: content,
        });

        console.log(response.text);

    }

    main();

### Go

    package main

    import (
      "context"
      "fmt"
      "io"
      "net/http"
      "os"
      "google.golang.org/genai"
    )

    func main() {

      ctx := context.Background()
      client, _ := genai.NewClient(ctx, &genai.ClientConfig{
        APIKey:  os.Getenv("GEMINI_API_KEY"),
        Backend: genai.BackendGeminiAPI,
      })

      pdfURL := "https://www.nasa.gov/wp-content/uploads/static/history/alsj/a17/A17_FlightPlan.pdf"
      localPdfPath := "A17_FlightPlan_downloaded.pdf"

      respHttp, _ := http.Get(pdfURL)
      defer respHttp.Body.Close()

      outFile, _ := os.Create(localPdfPath)
      defer outFile.Close()

      _, _ = io.Copy(outFile, respHttp.Body)

      uploadConfig := &genai.UploadFileConfig{MIMEType: "application/pdf"}
      uploadedFile, _ := client.Files.UploadFromPath(ctx, localPdfPath, uploadConfig)

      promptParts := []*genai.Part{
        genai.NewPartFromURI(uploadedFile.URI, uploadedFile.MIMEType),
        genai.NewPartFromText("Summarize this document"),
      }
      contents := []*genai.Content{
        genai.NewContentFromParts(promptParts, genai.RoleUser), // Specify role
      }

        result, _ := client.Models.GenerateContent(
            ctx,
            "gemini-2.5-flash",
            contents,
            nil,
        )

      fmt.Println(result.Text())
    }

### REST

    PDF_PATH="https://www.nasa.gov/wp-content/uploads/static/history/alsj/a17/A17_FlightPlan.pdf"
    DISPLAY_NAME="A17_FlightPlan"
    PROMPT="Summarize this document"

    # Download the PDF from the provided URL
    wget -O "${DISPLAY_NAME}.pdf" "${PDF_PATH}"

    MIME_TYPE=$(file -b --mime-type "${DISPLAY_NAME}.pdf")
    NUM_BYTES=$(wc -c < "${DISPLAY_NAME}.pdf")

    echo "MIME_TYPE: ${MIME_TYPE}"
    echo "NUM_BYTES: ${NUM_BYTES}"

    tmp_header_file=upload-header.tmp

    # Initial resumable request defining metadata.
    # The upload url is in the response headers dump them to a file.
    curl "${BASE_URL}/upload/v1beta/files?key=${GOOGLE_API_KEY}" \
      -D upload-header.tmp \
      -H "X-Goog-Upload-Protocol: resumable" \
      -H "X-Goog-Upload-Command: start" \
      -H "X-Goog-Upload-Header-Content-Length: ${NUM_BYTES}" \
      -H "X-Goog-Upload-Header-Content-Type: ${MIME_TYPE}" \
      -H "Content-Type: application/json" \
      -d "{'file': {'display_name': '${DISPLAY_NAME}'}}" 2> /dev/null

    upload_url=$(grep -i "x-goog-upload-url: " "${tmp_header_file}" | cut -d" " -f2 | tr -d "\r")
    rm "${tmp_header_file}"

    # Upload the actual bytes.
    curl "${upload_url}" \
      -H "Content-Length: ${NUM_BYTES}" \
      -H "X-Goog-Upload-Offset: 0" \
      -H "X-Goog-Upload-Command: upload, finalize" \
      --data-binary "@${DISPLAY_NAME}.pdf" 2> /dev/null > file_info.json

    file_uri=$(jq ".file.uri" file_info.json)
    echo "file_uri: ${file_uri}"

    # Now generate content using that file
    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=$GOOGLE_API_KEY" \
        -H 'Content-Type: application/json' \
        -X POST \
        -d '{
          "contents": [{
            "parts":[
              {"text": "'$PROMPT'"},
              {"file_data":{"mime_type": "application/pdf", "file_uri": '$file_uri'}}]
            }]
          }' 2> /dev/null > response.json

    cat response.json
    echo

    jq ".candidates[].content.parts[].text" response.json

    # Clean up the downloaded PDF
    rm "${DISPLAY_NAME}.pdf"

### Large PDFs stored locally

### Python

    from google import genai
    from google.genai import types
    import pathlib
    import httpx

    client = genai.Client()

    # Retrieve and encode the PDF byte
    file_path = pathlib.Path('large_file.pdf')

    # Upload the PDF using the File API
    sample_file = client.files.upload(
      file=file_path,
    )

    prompt="Summarize this document"

    response = client.models.generate_content(
      model="gemini-2.5-flash",
      contents=[sample_file, "Summarize this document"])
    print(response.text)

### JavaScript

    import { createPartFromUri, GoogleGenAI } from "@google/genai";

    const ai = new GoogleGenAI({ apiKey: "GEMINI_API_KEY" });

    async function main() {
        const file = await ai.files.upload({
            file: 'path-to-localfile.pdf'
            config: {
                displayName: 'A17_FlightPlan.pdf',
            },
        });

        // Wait for the file to be processed.
        let getFile = await ai.files.get({ name: file.name });
        while (getFile.state === 'PROCESSING') {
            getFile = await ai.files.get({ name: file.name });
            console.log(`current file status: ${getFile.state}`);
            console.log('File is still processing, retrying in 5 seconds');

            await new Promise((resolve) => {
                setTimeout(resolve, 5000);
            });
        }
        if (file.state === 'FAILED') {
            throw new Error('File processing failed.');
        }

        // Add the file to the contents.
        const content = [
            'Summarize this document',
        ];

        if (file.uri && file.mimeType) {
            const fileContent = createPartFromUri(file.uri, file.mimeType);
            content.push(fileContent);
        }

        const response = await ai.models.generateContent({
            model: 'gemini-2.5-flash',
            contents: content,
        });

        console.log(response.text);

    }

    main();

### Go

    package main

    import (
        "context"
        "fmt"
        "os"
        "google.golang.org/genai"
    )

    func main() {

        ctx := context.Background()
        client, _ := genai.NewClient(ctx, &genai.ClientConfig{
            APIKey:  os.Getenv("GEMINI_API_KEY"),
            Backend: genai.BackendGeminiAPI,
        })
        localPdfPath := "/path/to/file.pdf"

        uploadConfig := &genai.UploadFileConfig{MIMEType: "application/pdf"}
        uploadedFile, _ := client.Files.UploadFromPath(ctx, localPdfPath, uploadConfig)

        promptParts := []*genai.Part{
            genai.NewPartFromURI(uploadedFile.URI, uploadedFile.MIMEType),
            genai.NewPartFromText("Give me a summary of this pdf file."),
        }
        contents := []*genai.Content{
            genai.NewContentFromParts(promptParts, genai.RoleUser),
        }

        result, _ := client.Models.GenerateContent(
            ctx,
            "gemini-2.5-flash",
            contents,
            nil,
        )

        fmt.Println(result.Text())
    }

### REST

    NUM_BYTES=$(wc -c < "${PDF_PATH}")
    DISPLAY_NAME=TEXT
    tmp_header_file=upload-header.tmp

    # Initial resumable request defining metadata.
    # The upload url is in the response headers dump them to a file.
    curl "${BASE_URL}/upload/v1beta/files?key=${GEMINI_API_KEY}" \
      -D upload-header.tmp \
      -H "X-Goog-Upload-Protocol: resumable" \
      -H "X-Goog-Upload-Command: start" \
      -H "X-Goog-Upload-Header-Content-Length: ${NUM_BYTES}" \
      -H "X-Goog-Upload-Header-Content-Type: application/pdf" \
      -H "Content-Type: application/json" \
      -d "{'file': {'display_name': '${DISPLAY_NAME}'}}" 2> /dev/null

    upload_url=$(grep -i "x-goog-upload-url: " "${tmp_header_file}" | cut -d" " -f2 | tr -d "\r")
    rm "${tmp_header_file}"

    # Upload the actual bytes.
    curl "${upload_url}" \
      -H "Content-Length: ${NUM_BYTES}" \
      -H "X-Goog-Upload-Offset: 0" \
      -H "X-Goog-Upload-Command: upload, finalize" \
      --data-binary "@${PDF_PATH}" 2> /dev/null > file_info.json

    file_uri=$(jq ".file.uri" file_info.json)
    echo file_uri=$file_uri

    # Now generate content using that file
    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=$GOOGLE_API_KEY" \
        -H 'Content-Type: application/json' \
        -X POST \
        -d '{
          "contents": [{
            "parts":[
              {"text": "Can you add a few more lines to this poem?"},
              {"file_data":{"mime_type": "application/pdf", "file_uri": '$file_uri'}}]
            }]
          }' 2> /dev/null > response.json

    cat response.json
    echo

    jq ".candidates[].content.parts[].text" response.json

You can verify the API successfully stored the uploaded file and get its metadata by calling[`files.get`](https://ai.google.dev/api/rest/v1beta/files/get). Only the`name`(and by extension, the`uri`) are unique.  

### Python

    from google import genai
    import pathlib

    client = genai.Client()

    fpath = pathlib.Path('example.txt')
    fpath.write_text('hello')

    file = client.files.upload(file='example.txt')

    file_info = client.files.get(name=file.name)
    print(file_info.model_dump_json(indent=4))

### REST

    name=$(jq ".file.name" file_info.json)
    # Get the file of interest to check state
    curl https://generativelanguage.googleapis.com/v1beta/files/$name > file_info.json
    # Print some information about the file you got
    name=$(jq ".file.name" file_info.json)
    echo name=$name
    file_uri=$(jq ".file.uri" file_info.json)
    echo file_uri=$file_uri

## Passing multiple PDFs

The Gemini API is capable of processing multiple PDF documents (up to 1000 pages) in a single request, as long as the combined size of the documents and the text prompt stays within the model's context window.  

### Python

    from google import genai
    import io
    import httpx

    client = genai.Client()

    doc_url_1 = "https://arxiv.org/pdf/2312.11805"
    doc_url_2 = "https://arxiv.org/pdf/2403.05530"

    # Retrieve and upload both PDFs using the File API
    doc_data_1 = io.BytesIO(httpx.get(doc_url_1).content)
    doc_data_2 = io.BytesIO(httpx.get(doc_url_2).content)

    sample_pdf_1 = client.files.upload(
      file=doc_data_1,
      config=dict(mime_type='application/pdf')
    )
    sample_pdf_2 = client.files.upload(
      file=doc_data_2,
      config=dict(mime_type='application/pdf')
    )

    prompt = "What is the difference between each of the main benchmarks between these two papers? Output these in a table."

    response = client.models.generate_content(
      model="gemini-2.5-flash",
      contents=[sample_pdf_1, sample_pdf_2, prompt])
    print(response.text)

### JavaScript

    import { createPartFromUri, GoogleGenAI } from "@google/genai";

    const ai = new GoogleGenAI({ apiKey: "GEMINI_API_KEY" });

    async function uploadRemotePDF(url, displayName) {
        const pdfBuffer = await fetch(url)
            .then((response) => response.arrayBuffer());

        const fileBlob = new Blob([pdfBuffer], { type: 'application/pdf' });

        const file = await ai.files.upload({
            file: fileBlob,
            config: {
                displayName: displayName,
            },
        });

        // Wait for the file to be processed.
        let getFile = await ai.files.get({ name: file.name });
        while (getFile.state === 'PROCESSING') {
            getFile = await ai.files.get({ name: file.name });
            console.log(`current file status: ${getFile.state}`);
            console.log('File is still processing, retrying in 5 seconds');

            await new Promise((resolve) => {
                setTimeout(resolve, 5000);
            });
        }
        if (file.state === 'FAILED') {
            throw new Error('File processing failed.');
        }

        return file;
    }

    async function main() {
        const content = [
            'What is the difference between each of the main benchmarks between these two papers? Output these in a table.',
        ];

        let file1 = await uploadRemotePDF("https://arxiv.org/pdf/2312.11805", "PDF 1")
        if (file1.uri && file1.mimeType) {
            const fileContent = createPartFromUri(file1.uri, file1.mimeType);
            content.push(fileContent);
        }
        let file2 = await uploadRemotePDF("https://arxiv.org/pdf/2403.05530", "PDF 2")
        if (file2.uri && file2.mimeType) {
            const fileContent = createPartFromUri(file2.uri, file2.mimeType);
            content.push(fileContent);
        }

        const response = await ai.models.generateContent({
            model: 'gemini-2.5-flash',
            contents: content,
        });

        console.log(response.text);
    }

    main();

### Go

    package main

    import (
        "context"
        "fmt"
        "io"
        "net/http"
        "os"
        "google.golang.org/genai"
    )

    func main() {

        ctx := context.Background()
        client, _ := genai.NewClient(ctx, &genai.ClientConfig{
            APIKey:  os.Getenv("GEMINI_API_KEY"),
            Backend: genai.BackendGeminiAPI,
        })

        docUrl1 := "https://arxiv.org/pdf/2312.11805"
        docUrl2 := "https://arxiv.org/pdf/2403.05530"
        localPath1 := "doc1_downloaded.pdf"
        localPath2 := "doc2_downloaded.pdf"

        respHttp1, _ := http.Get(docUrl1)
        defer respHttp1.Body.Close()

        outFile1, _ := os.Create(localPath1)
        _, _ = io.Copy(outFile1, respHttp1.Body)
        outFile1.Close()

        respHttp2, _ := http.Get(docUrl2)
        defer respHttp2.Body.Close()

        outFile2, _ := os.Create(localPath2)
        _, _ = io.Copy(outFile2, respHttp2.Body)
        outFile2.Close()

        uploadConfig1 := &genai.UploadFileConfig{MIMEType: "application/pdf"}
        uploadedFile1, _ := client.Files.UploadFromPath(ctx, localPath1, uploadConfig1)

        uploadConfig2 := &genai.UploadFileConfig{MIMEType: "application/pdf"}
        uploadedFile2, _ := client.Files.UploadFromPath(ctx, localPath2, uploadConfig2)

        promptParts := []*genai.Part{
            genai.NewPartFromURI(uploadedFile1.URI, uploadedFile1.MIMEType),
            genai.NewPartFromURI(uploadedFile2.URI, uploadedFile2.MIMEType),
            genai.NewPartFromText("What is the difference between each of the " +
                                  "main benchmarks between these two papers? " +
                                  "Output these in a table."),
        }
        contents := []*genai.Content{
            genai.NewContentFromParts(promptParts, genai.RoleUser),
        }

        modelName := "gemini-2.5-flash"
        result, _ := client.Models.GenerateContent(
            ctx,
            modelName,
            contents,
            nil,
        )

        fmt.Println(result.Text())
    }

### REST

    DOC_URL_1="https://arxiv.org/pdf/2312.11805"
    DOC_URL_2="https://arxiv.org/pdf/2403.05530"
    DISPLAY_NAME_1="Gemini_paper"
    DISPLAY_NAME_2="Gemini_1.5_paper"
    PROMPT="What is the difference between each of the main benchmarks between these two papers? Output these in a table."

    # Function to download and upload a PDF
    upload_pdf() {
      local doc_url="$1"
      local display_name="$2"

      # Download the PDF
      wget -O "${display_name}.pdf" "${doc_url}"

      local MIME_TYPE=$(file -b --mime-type "${display_name}.pdf")
      local NUM_BYTES=$(wc -c < "${display_name}.pdf")

      echo "MIME_TYPE: ${MIME_TYPE}"
      echo "NUM_BYTES: ${NUM_BYTES}"

      local tmp_header_file=upload-header.tmp

      # Initial resumable request
      curl "${BASE_URL}/upload/v1beta/files?key=${GOOGLE_API_KEY}" \
        -D "${tmp_header_file}" \
        -H "X-Goog-Upload-Protocol: resumable" \
        -H "X-Goog-Upload-Command: start" \
        -H "X-Goog-Upload-Header-Content-Length: ${NUM_BYTES}" \
        -H "X-Goog-Upload-Header-Content-Type: ${MIME_TYPE}" \
        -H "Content-Type: application/json" \
        -d "{'file': {'display_name': '${display_name}'}}" 2> /dev/null

      local upload_url=$(grep -i "x-goog-upload-url: " "${tmp_header_file}" | cut -d" " -f2 | tr -d "\r")
      rm "${tmp_header_file}"

      # Upload the PDF
      curl "${upload_url}" \
        -H "Content-Length: ${NUM_BYTES}" \
        -H "X-Goog-Upload-Offset: 0" \
        -H "X-Goog-Upload-Command: upload, finalize" \
        --data-binary "@${display_name}.pdf" 2> /dev/null > "file_info_${display_name}.json"

      local file_uri=$(jq ".file.uri" "file_info_${display_name}.json")
      echo "file_uri for ${display_name}: ${file_uri}"

      # Clean up the downloaded PDF
      rm "${display_name}.pdf"

      echo "${file_uri}"
    }

    # Upload the first PDF
    file_uri_1=$(upload_pdf "${DOC_URL_1}" "${DISPLAY_NAME_1}")

    # Upload the second PDF
    file_uri_2=$(upload_pdf "${DOC_URL_2}" "${DISPLAY_NAME_2}")

    # Now generate content using both files
    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=$GOOGLE_API_KEY" \
        -H 'Content-Type: application/json' \
        -X POST \
        -d '{
          "contents": [{
            "parts":[
              {"file_data": {"mime_type": "application/pdf", "file_uri": '$file_uri_1'}},
              {"file_data": {"mime_type": "application/pdf", "file_uri": '$file_uri_2'}},
              {"text": "'$PROMPT'"}
            ]
          }]
        }' 2> /dev/null > response.json

    cat response.json
    echo

    jq ".candidates[].content.parts[].text" response.json

## Technical details

Gemini supports PDF files up to 50MB or 1000 pages. This limit applies to both inline data and Files API uploads. Each document page is equivalent to 258 tokens.

While there are no specific limits to the number of pixels in a document besides the model's[context window](https://ai.google.dev/gemini-api/docs/long-context), larger pages are scaled down to a maximum resolution of 3072 x 3072 while preserving their original aspect ratio, while smaller pages are scaled up to 768 x 768 pixels. There is no cost reduction for pages at lower sizes, other than bandwidth, or performance improvement for pages at higher resolution.

### Gemini 3 models

Gemini 3 introduces granular control over multimodal vision processing with the`media_resolution`parameter. You can now set the resolution to low, medium, or high per individual media part. With this addition, the processing of PDF documents has been updated:

1. **Native text inclusion:**Text natively embedded in the PDF is extracted and provided to the model.
2. **Billing \& token reporting:**
   - You are**not charged** for tokens originating from the extracted**native text**in PDFs.
   - In the`usage_metadata`section of the API response, tokens generated from processing PDF pages (as images) are now counted under the`IMAGE`modality, not a separate`DOCUMENT`modality as in some earlier versions.

For more details about the media resolution parameter, see the[Media resolution](https://ai.google.dev/gemini-api/docs/media-resolution)guide.

### Document types

Technically, you can pass other MIME types for document understanding, like TXT, Markdown, HTML, XML, etc. However, document vision***only meaningfully understands PDFs***. Other types will be extracted as pure text, and the model won't be able to interpret what we see in the rendering of those files. Any file-type specifics like charts, diagrams, HTML tags, Markdown formatting, etc., will be lost.

### Best practices

For best results:

- Rotate pages to the correct orientation before uploading.
- Avoid blurry pages.
- If using a single page, place the text prompt after the page.

## What's next

To learn more, see the following resources:

- [File prompting strategies](https://ai.google.dev/gemini-api/docs/files#prompt-guide): The Gemini API supports prompting with text, image, audio, and video data, also known as multimodal prompting.
- [System instructions](https://ai.google.dev/gemini-api/docs/text-generation#system-instructions): System instructions let you steer the behavior of the model based on your specific needs and use cases.Many Gemini models come with large context windows of 1 million or more tokens.
Historically, large language models (LLMs) were significantly limited by
the amount of text (or tokens) that could be passed to the model at one time.
The Gemini long context window unlocks many new use cases and developer
paradigms.

The code you already use for cases like [text
generation](https://ai.google.dev/gemini-api/docs/text-generation) or [multimodal
inputs](https://ai.google.dev/gemini-api/docs/vision) will work without any changes with long context.

This document gives you an overview of what you can achieve using models with
context windows of 1M and more tokens. The page gives a brief overview of
a context window, and explores how developers should think about long context,
various real world use cases for long context, and ways to optimize the usage
of long context.

For the context window sizes of specific models, see the
[Models](https://ai.google.dev/gemini-api/docs/models) page.

## What is a context window?

The basic way you use the Gemini models is by passing information (context)
to the model, which will subsequently generate a response. An analogy for the
context window is short term memory. There is a limited amount of information
that can be stored in someone's short term memory, and the same is true for
generative models.

You can read more about how models work under the hood in our [generative models
guide](https://ai.google.dev/gemini-api/docs/prompting-strategies#under-the-hood).

## Getting started with long context

Earlier versions of generative models were only able to process 8,000
tokens at a time. Newer models pushed this further by accepting 32,000 or even
128,000 tokens. Gemini is the first model capable of accepting 1 million tokens.

In practice, 1 million tokens would look like:

- 50,000 lines of code (with the standard 80 characters per line)
- All the text messages you have sent in the last 5 years
- 8 average length English novels
- Transcripts of over 200 average length podcast episodes

The more limited context windows common in many other models often require
strategies like arbitrarily dropping old messages, summarizing content, using
RAG with vector databases, or filtering prompts to save tokens.

While these techniques remain valuable in specific scenarios, Gemini's extensive
context window invites a more direct approach: providing all relevant
information upfront. Because Gemini models were purpose-built with massive
context capabilities, they demonstrate powerful in-context learning. For
example, using only in-context instructional materials (a 500-page reference
grammar, a dictionary, and ≈400 parallel sentences), Gemini
[learned to translate](https://storage.googleapis.com/deepmind-media/gemini/gemini_v1_5_report.pdf)
from English to Kalamang---a Papuan language with
fewer than 200 speakers---with quality similar to a human learner using the same
materials. This illustrates the paradigm shift enabled by Gemini's long context,
empowering new possibilities through robust in-context learning.

## Long context use cases

While the standard use case for most generative models is still text input, the
Gemini model family enables a new paradigm of multimodal use cases. These
models can natively understand text, video, audio, and images. They are
accompanied by the [Gemini API that takes in multimodal file
types](https://ai.google.dev/gemini-api/docs/prompting_with_media) for
convenience.

### Long form text

Text has proved to be the layer of intelligence underpinning much of the
momentum around LLMs. As mentioned earlier, much of the practical limitation of
LLMs was because of not having a large enough context window to do certain
tasks. This led to the rapid adoption of retrieval augmented generation (RAG)
and other techniques which dynamically provide the model with relevant
contextual information. Now, with larger and larger context windows, there are
new techniques becoming available which unlock new use cases.

Some emerging and standard use cases for text based long context include:

- Summarizing large corpuses of text
  - Previous summarization options with smaller context models would require a sliding window or another technique to keep state of previous sections as new tokens are passed to the model
- Question and answering
  - Historically this was only possible with RAG given the limited amount of context and models' factual recall being low
- Agentic workflows
  - Text is the underpinning of how agents keep state of what they have done and what they need to do; not having enough information about the world and the agent's goal is a limitation on the reliability of agents

[Many-shot in-context learning](https://arxiv.org/pdf/2404.11018) is one of the
most unique capabilities unlocked by long context models. Research has shown
that taking the common "single shot" or "multi-shot" example paradigm, where the
model is presented with one or a few examples of a task, and scaling that up to
hundreds, thousands, or even hundreds of thousands of examples, can lead to
novel model capabilities. This many-shot approach has also been shown to perform
similarly to models which were fine-tuned for a specific task. For use cases
where a Gemini model's performance is not yet sufficient for a production
rollout, you can try the many-shot approach. As you might explore later in the
long context optimization section, context caching makes this type of high input
token workload much more economically feasible and even lower latency in some
cases.

### Long form video

Video content's utility has long been constrained by the lack of accessibility
of the medium itself. It was hard to skim the content, transcripts often failed
to capture the nuance of a video, and most tools don't process image, text, and
audio together. With Gemini, the long-context text capabilities translate to
the ability to reason and answer questions about multimodal inputs with
sustained performance.

Some emerging and standard use cases for video long context include:

- Video question and answering
- Video memory, as shown with [Google's Project Astra](https://deepmind.google/technologies/gemini/project-astra/)
- Video captioning
- Video recommendation systems, by enriching existing metadata with new multimodal understanding
- Video customization, by looking at a corpus of data and associated video metadata and then removing parts of videos that are not relevant to the viewer
- Video content moderation
- Real-time video processing

When working with videos, it is important to consider how the [videos are
processed into tokens](https://ai.google.dev/gemini-api/docs/tokens#media-token), which affects
billing and usage limits. You can learn more about prompting with video files in
the [Prompting
guide](https://ai.google.dev/gemini-api/docs/prompting_with_media?lang=python#prompting-with-videos).

### Long form audio

The Gemini models were the first natively multimodal large language models
that could understand audio. Historically, the typical developer workflow would
involve stringing together multiple domain specific models, like a
speech-to-text model and a text-to-text model, in order to process audio. This
led to additional latency required by performing multiple round-trip requests
and decreased performance usually attributed to disconnected architectures of
the multiple model setup.

Some emerging and standard use cases for audio context include:

- Real-time transcription and translation
- Podcast / video question and answering
- Meeting transcription and summarization
- Voice assistants

You can learn more about prompting with audio files in the [Prompting
guide](https://ai.google.dev/gemini-api/docs/prompting_with_media?lang=python#prompting-with-videos).

## Long context optimizations

The primary optimization when working with long context and the Gemini
models is to use [context
caching](https://ai.google.dev/gemini-api/docs/caching). Beyond the previous
impossibility of processing lots of tokens in a single request, the other main
constraint was the cost. If you have a "chat with your data" app where a user
uploads 10 PDFs, a video, and some work documents, you would historically have
to work with a more complex retrieval augmented generation (RAG) tool /
framework in order to process these requests and pay a significant amount for
tokens moved into the context window. Now, you can cache the files the user
uploads and pay to store them on a per hour basis. The input / output cost per
request with Gemini Flash for example is \~4x less than the standard
input / output cost, so if
the user chats with their data enough, it becomes a huge cost saving for you as
the developer.

## Long context limitations

In various sections of this guide, we talked about how Gemini models achieve
high performance across various needle-in-a-haystack retrieval evals. These
tests consider the most basic setup, where you have a single needle you are
looking for. In cases where you might have multiple "needles" or specific pieces
of information you are looking for, the model does not perform with the same
accuracy. Performance can vary to a wide degree depending on the context. This
is important to consider as there is an inherent tradeoff between getting the
right information retrieved and cost. You can get \~99% on a single query, but
you have to pay the input token cost every time you send that query. So for 100
pieces of information to be retrieved, if you needed 99% performance, you would
likely need to send 100 requests. This is a good example of where context
caching can significantly reduce the cost associated with using Gemini models
while keeping the performance high.

## FAQs

### Where is the best place to put my query in the context window?

In most cases, especially if the total context is long, the model's
performance will be better if you put your query / question at the end of the
prompt (after all the other context).

### Do I lose model performance when I add more tokens to a query?

Generally, if you don't need tokens to be passed to the model, it is best to
avoid passing them. However, if you have a large chunk of tokens with some
information and want to ask questions about that information, the model is
highly capable of extracting that information (up to 99% accuracy in many
cases).

### How can I lower my cost with long-context queries?

If you have a similar set of tokens / context that you want to re-use many
times, [context caching](https://ai.google.dev/gemini-api/docs/caching) can help reduce the costs
associated with asking questions about that information.

### Does the context length affect the model latency?

There is some fixed amount of latency in any given request, regardless of the
size, but generally longer queries will have higher latency (time to first
token).<br />

You can configure Gemini models to generate responses that adhere to a provided JSON Schema. This capability guarantees predictable and parsable results, ensures format and type-safety, enables the programmatic detection of refusals, and simplifies prompting.

Using structured outputs is ideal for a wide range of applications:

- **Data extraction:**Pull specific information from unstructured text, like extracting names, dates, and amounts from an invoice.
- **Structured classification:**Classify text into predefined categories and assign structured labels, such as categorizing customer feedback by sentiment and topic.
- **Agentic workflows:**Generate structured data that can be used to call other tools or APIs, like creating a character sheet for a game or filling out a form.

In addition to supporting JSON Schema in the REST API, the Google GenAI SDKs for Python and JavaScript also make it easy to define object schemas using[Pydantic](https://docs.pydantic.dev/latest/)and[Zod](https://zod.dev/), respectively. The example below demonstrates how to extract information from unstructured text that conforms to a schema defined in code.

Recipe ExtractorContent ModerationRecursive Structures

This example demonstrates how to extract structured data from text using basic JSON Schema types like`object`,`array`,`string`, and`integer`.  

### Python

    from google import genai
    from pydantic import BaseModel, Field
    from typing import List, Optional

    class Ingredient(BaseModel):
        name: str = Field(description="Name of the ingredient.")
        quantity: str = Field(description="Quantity of the ingredient, including units.")

    class Recipe(BaseModel):
        recipe_name: str = Field(description="The name of the recipe.")
        prep_time_minutes: Optional[int] = Field(description="Optional time in minutes to prepare the recipe.")
        ingredients: List[Ingredient]
        instructions: List[str]

    client = genai.Client()

    prompt = """
    Please extract the recipe from the following text.
    The user wants to make delicious chocolate chip cookies.
    They need 2 and 1/4 cups of all-purpose flour, 1 teaspoon of baking soda,
    1 teaspoon of salt, 1 cup of unsalted butter (softened), 3/4 cup of granulated sugar,
    3/4 cup of packed brown sugar, 1 teaspoon of vanilla extract, and 2 large eggs.
    For the best part, they'll need 2 cups of semisweet chocolate chips.
    First, preheat the oven to 375°F (190°C). Then, in a small bowl, whisk together the flour,
    baking soda, and salt. In a large bowl, cream together the butter, granulated sugar, and brown sugar
    until light and fluffy. Beat in the vanilla and eggs, one at a time. Gradually beat in the dry
    ingredients until just combined. Finally, stir in the chocolate chips. Drop by rounded tablespoons
    onto ungreased baking sheets and bake for 9 to 11 minutes.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": Recipe.model_json_schema(),
        },
    )

    recipe = Recipe.model_validate_json(response.text)
    print(recipe)

### JavaScript

    import { GoogleGenAI } from "@google/genai";
    import { z } from "zod";
    import { zodToJsonSchema } from "zod-to-json-schema";

    const ingredientSchema = z.object({
      name: z.string().describe("Name of the ingredient."),
      quantity: z.string().describe("Quantity of the ingredient, including units."),
    });

    const recipeSchema = z.object({
      recipe_name: z.string().describe("The name of the recipe."),
      prep_time_minutes: z.number().optional().describe("Optional time in minutes to prepare the recipe."),
      ingredients: z.array(ingredientSchema),
      instructions: z.array(z.string()),
    });

    const ai = new GoogleGenAI({});

    const prompt = `
    Please extract the recipe from the following text.
    The user wants to make delicious chocolate chip cookies.
    They need 2 and 1/4 cups of all-purpose flour, 1 teaspoon of baking soda,
    1 teaspoon of salt, 1 cup of unsalted butter (softened), 3/4 cup of granulated sugar,
    3/4 cup of packed brown sugar, 1 teaspoon of vanilla extract, and 2 large eggs.
    For the best part, they'll need 2 cups of semisweet chocolate chips.
    First, preheat the oven to 375°F (190°C). Then, in a small bowl, whisk together the flour,
    baking soda, and salt. In a large bowl, cream together the butter, granulated sugar, and brown sugar
    until light and fluffy. Beat in the vanilla and eggs, one at a time. Gradually beat in the dry
    ingredients until just combined. Finally, stir in the chocolate chips. Drop by rounded tablespoons
    onto ungreased baking sheets and bake for 9 to 11 minutes.
    `;

    const response = await ai.models.generateContent({
      model: "gemini-2.5-flash",
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseJsonSchema: zodToJsonSchema(recipeSchema),
      },
    });

    const recipe = recipeSchema.parse(JSON.parse(response.text));
    console.log(recipe);

### Go

    package main

    import (
        "context"
        "fmt"
        "log"

        "google.golang.org/genai"
    )

    func main() {
        ctx := context.Background()
        client, err := genai.NewClient(ctx, nil)
        if err != nil {
            log.Fatal(err)
        }

        prompt := `
      Please extract the recipe from the following text.
      The user wants to make delicious chocolate chip cookies.
      They need 2 and 1/4 cups of all-purpose flour, 1 teaspoon of baking soda,
      1 teaspoon of salt, 1 cup of unsalted butter (softened), 3/4 cup of granulated sugar,
      3/4 cup of packed brown sugar, 1 teaspoon of vanilla extract, and 2 large eggs.
      For the best part, they'll need 2 cups of semisweet chocolate chips.
      First, preheat the oven to 375°F (190°C). Then, in a small bowl, whisk together the flour,
      baking soda, and salt. In a large bowl, cream together the butter, granulated sugar, and brown sugar
      until light and fluffy. Beat in the vanilla and eggs, one at a time. Gradually beat in the dry
      ingredients until just combined. Finally, stir in the chocolate chips. Drop by rounded tablespoons
      onto ungreased baking sheets and bake for 9 to 11 minutes.
      `
        config := &genai.GenerateContentConfig{
            ResponseMIMEType: "application/json",
            ResponseJsonSchema: map[string]any{
                "type": "object",
                "properties": map[string]any{
                    "recipe_name": map[string]any{
                        "type":        "string",
                        "description": "The name of the recipe.",
                    },
                    "prep_time_minutes": map[string]any{
                        "type":        "integer",
                        "description": "Optional time in minutes to prepare the recipe.",
                    },
                    "ingredients": map[string]any{
                        "type": "array",
                        "items": map[string]any{
                            "type": "object",
                            "properties": map[string]any{
                                "name": map[string]any{
                                    "type":        "string",
                                    "description": "Name of the ingredient.",
                                },
                                "quantity": map[string]any{
                                    "type":        "string",
                                    "description": "Quantity of the ingredient, including units.",
                                },
                            },
                            "required": []string{"name", "quantity"},
                        },
                    },
                    "instructions": map[string]any{
                        "type":  "array",
                        "items": map[string]any{"type": "string"},
                    },
                },
                "required": []string{"recipe_name", "ingredients", "instructions"},
            },
        }

        result, err := client.Models.GenerateContent(
            ctx,
            "gemini-2.5-flash",
            genai.Text(prompt),
            config,
        )
        if err != nil {
            log.Fatal(err)
        }
        fmt.Println(result.Text())
    }

### REST

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" \
        -H "x-goog-api-key: $GEMINI_API_KEY" \
        -H 'Content-Type: application/json' \
        -X POST \
        -d '{
          "contents": [{
            "parts":[
              { "text": "Please extract the recipe from the following text.\nThe user wants to make delicious chocolate chip cookies.\nThey need 2 and 1/4 cups of all-purpose flour, 1 teaspoon of baking soda,\n1 teaspoon of salt, 1 cup of unsalted butter (softened), 3/4 cup of granulated sugar,\n3/4 cup of packed brown sugar, 1 teaspoon of vanilla extract, and 2 large eggs.\nFor the best part, they will need 2 cups of semisweet chocolate chips.\nFirst, preheat the oven to 375°F (190°C). Then, in a small bowl, whisk together the flour,\nbaking soda, and salt. In a large bowl, cream together the butter, granulated sugar, and brown sugar\nuntil light and fluffy. Beat in the vanilla and eggs, one at a time. Gradually beat in the dry\ningredients until just combined. Finally, stir in the chocolate chips. Drop by rounded tablespoons\nonto ungreased baking sheets and bake for 9 to 11 minutes." }
            ]
          }],
          "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": {
              "type": "object",
              "properties": {
                "recipe_name": {
                  "type": "string",
                  "description": "The name of the recipe."
                },
                "prep_time_minutes": {
                    "type": "integer",
                    "description": "Optional time in minutes to prepare the recipe."
                },
                "ingredients": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "name": { "type": "string", "description": "Name of the ingredient."},
                      "quantity": { "type": "string", "description": "Quantity of the ingredient, including units."}
                    },
                    "required": ["name", "quantity"]
                  }
                },
                "instructions": {
                  "type": "array",
                  "items": { "type": "string" }
                }
              },
              "required": ["recipe_name", "ingredients", "instructions"]
            }
          }
        }'

**Example Response:**  

    {
      "recipe_name": "Delicious Chocolate Chip Cookies",
      "ingredients": [
        {
          "name": "all-purpose flour",
          "quantity": "2 and 1/4 cups"
        },
        {
          "name": "baking soda",
          "quantity": "1 teaspoon"
        },
        {
          "name": "salt",
          "quantity": "1 teaspoon"
        },
        {
          "name": "unsalted butter (softened)",
          "quantity": "1 cup"
        },
        {
          "name": "granulated sugar",
          "quantity": "3/4 cup"
        },
        {
          "name": "packed brown sugar",
          "quantity": "3/4 cup"
        },
        {
          "name": "vanilla extract",
          "quantity": "1 teaspoon"
        },
        {
          "name": "large eggs",
          "quantity": "2"
        },
        {
          "name": "semisweet chocolate chips",
          "quantity": "2 cups"
        }
      ],
      "instructions": [
        "Preheat the oven to 375°F (190°C).",
        "In a small bowl, whisk together the flour, baking soda, and salt.",
        "In a large bowl, cream together the butter, granulated sugar, and brown sugar until light and fluffy.",
        "Beat in the vanilla and eggs, one at a time.",
        "Gradually beat in the dry ingredients until just combined.",
        "Stir in the chocolate chips.",
        "Drop by rounded tablespoons onto ungreased baking sheets and bake for 9 to 11 minutes."
      ]
    }

## Streaming

You can stream structured outputs, which allows you to start processing the response as it's being generated, without having to wait for the entire output to be complete. This can improve the perceived performance of your application.

The streamed chunks will be valid partial JSON strings, which can be concatenated to form the final, complete JSON object.  

### Python

    from google import genai
    from pydantic import BaseModel, Field
    from typing import Literal

    class Feedback(BaseModel):
        sentiment: Literal["positive", "neutral", "negative"]
        summary: str

    client = genai.Client()
    prompt = "The new UI is incredibly intuitive and visually appealing. Great job. Add a very long summary to test streaming!"

    response_stream = client.models.generate_content_stream(
        model="gemini-2.5-flash",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": Feedback.model_json_schema(),
        },
    )

    for chunk in response_stream:
        print(chunk.candidates[0].content.parts[0].text)

### JavaScript

    import { GoogleGenAI } from "@google/genai";
    import { z } from "zod";
    import { zodToJsonSchema } from "zod-to-json-schema";

    const ai = new GoogleGenAI({});
    const prompt = "The new UI is incredibly intuitive and visually appealing. Great job! Add a very long summary to test streaming!";

    const feedbackSchema = z.object({
      sentiment: z.enum(["positive", "neutral", "negative"]),
      summary: z.string(),
    });

    const stream = await ai.models.generateContentStream({
      model: "gemini-2.5-flash",
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseJsonSchema: zodToJsonSchema(feedbackSchema),
      },
    });

    for await (const chunk of stream) {
      console.log(chunk.candidates[0].content.parts[0].text)
    }

## Structured outputs with tools

| **Preview:** This is a feature available only for the Gemini 3 series models,`gemini-3-pro-preview`and`gemini-3-flash-preview`.

Gemini 3 lets you combine Structured Outputs with built-in tools, including[Grounding with Google Search](https://ai.google.dev/gemini-api/docs/google-search),[URL Context](https://ai.google.dev/gemini-api/docs/url-context), and[Code Execution](https://ai.google.dev/gemini-api/docs/code-execution).  

### Python

    from google import genai
    from pydantic import BaseModel, Field
    from typing import List

    class MatchResult(BaseModel):
        winner: str = Field(description="The name of the winner.")
        final_match_score: str = Field(description="The final match score.")
        scorers: List[str] = Field(description="The name of the scorer.")

    client = genai.Client()

    response = client.models.generate_content(
        model="gemini-3-pro-preview",
        contents="Search for all details for the latest Euro.",
        config={
            "tools": [
                {"google_search": {}},
                {"url_context": {}}
            ],
            "response_mime_type": "application/json",
            "response_json_schema": MatchResult.model_json_schema(),
        },  
    )

    result = MatchResult.model_validate_json(response.text)
    print(result)

### JavaScript

    import { GoogleGenAI } from "@google/genai";
    import { z } from "zod";
    import { zodToJsonSchema } from "zod-to-json-schema";

    const ai = new GoogleGenAI({});

    const matchSchema = z.object({
      winner: z.string().describe("The name of the winner."),
      final_match_score: z.string().describe("The final score."),
      scorers: z.array(z.string()).describe("The name of the scorer.")
    });

    async function run() {
      const response = await ai.models.generateContent({
        model: "gemini-3-pro-preview",
        contents: "Search for all details for the latest Euro.",
        config: {
          tools: [
            { googleSearch: {} },
            { urlContext: {} }
          ],
          responseMimeType: "application/json",
          responseJsonSchema: zodToJsonSchema(matchSchema),
        },
      });

      const match = matchSchema.parse(JSON.parse(response.text));
      console.log(match);
    }

    run();

### REST

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-preview:generateContent" \
      -H "x-goog-api-key: $GEMINI_API_KEY" \
      -H 'Content-Type: application/json' \
      -X POST \
      -d '{
        "contents": [{
          "parts": [{"text": "Search for all details for the latest Euro."}]
        }],
        "tools": [
          {"googleSearch": {}},
          {"urlContext": {}}
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": {
                "type": "object",
                "properties": {
                    "winner": {"type": "string", "description": "The name of the winner."},
                    "final_match_score": {"type": "string", "description": "The final score."},
                    "scorers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "The name of the scorer."
                    }
                },
                "required": ["winner", "final_match_score", "scorers"]
            }
        }
      }'

## JSON schema support

To generate a JSON object, set the`response_mime_type`in the generation configuration to`application/json`and provide a`response_json_schema`. The schema must be a valid[JSON Schema](https://json-schema.org/)that describes the desired output format.

The model will then generate a response that is a syntactically valid JSON string matching the provided schema. When using structured outputs, the model will produce outputs in the same order as the keys in the schema.

Gemini's structured output mode supports a subset of the[JSON Schema](https://json-schema.org)specification.

The following values of`type`are supported:

- **`string`**: For text.
- **`number`**: For floating-point numbers.
- **`integer`**: For whole numbers.
- **`boolean`**: For true/false values.
- **`object`**: For structured data with key-value pairs.
- **`array`**: For lists of items.
- **`null`** : To allow a property to be null, include`"null"`in the type array (e.g.,`{"type": ["string", "null"]}`).

These descriptive properties help guide the model:

- **`title`**: A short description of a property.
- **`description`**: A longer and more detailed description of a property.

### Type-specific properties

**For`object`values:**

- **`properties`**: An object where each key is a property name and each value is a schema for that property.
- **`required`**: An array of strings, listing which properties are mandatory.
- **`additionalProperties`** : Controls whether properties not listed in`properties`are allowed. Can be a boolean or a schema.

**For`string`values:**

- **`enum`**: Lists a specific set of possible strings for classification tasks.
- **`format`** : Specifies a syntax for the string, such as`date-time`,`date`,`time`.

**For`number`and`integer`values:**

- **`enum`**: Lists a specific set of possible numeric values.
- **`minimum`**: The minimum inclusive value.
- **`maximum`**: The maximum inclusive value.

**For`array`values:**

- **`items`**: Defines the schema for all items in the array.
- **`prefixItems`**: Defines a list of schemas for the first N items, allowing for tuple-like structures.
- **`minItems`**: The minimum number of items in the array.
- **`maxItems`**: The maximum number of items in the array.

## Model support

The following models support structured output:

|         Model          | Structured Outputs |
|------------------------|--------------------|
| Gemini 3 Pro Preview   | ✔️                 |
| Gemini 3 Flash Preview | ✔️                 |
| Gemini 2.5 Pro         | ✔️                 |
| Gemini 2.5 Flash       | ✔️                 |
| Gemini 2.5 Flash-Lite  | ✔️                 |
| Gemini 2.0 Flash       | ✔️\*               |
| Gemini 2.0 Flash-Lite  | ✔️\*               |

*\* Note that Gemini 2.0 requires an explicit`propertyOrdering`list within the JSON input to define the preferred structure. You can find an example in this[cookbook](https://github.com/google-gemini/cookbook/blob/main/examples/Pdf_structured_outputs_on_invoices_and_forms.ipynb).*

## Structured outputs vs. function calling

Both structured outputs and function calling use JSON schemas, but they serve different purposes:

|        Feature         |                                                                                  Primary Use Case                                                                                  |
|------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Structured Outputs** | **Formatting the final response to the user.** Use this when you want the model's*answer*to be in a specific format (e.g., extracting data from a document to save to a database). |
| **Function Calling**   | **Taking action during the conversation.** Use this when the model needs to*ask you*to perform a task (e.g., "get current weather") before it can provide a final answer.          |

## Best practices

- **Clear descriptions:** Use the`description`field in your schema to provide clear instructions to the model about what each property represents. This is crucial for guiding the model's output.
- **Strong typing:** Use specific types (`integer`,`string`,`enum`) whenever possible. If a parameter has a limited set of valid values, use an`enum`.
- **Prompt engineering:**Clearly state in your prompt what you want the model to do. For example, "Extract the following information from the text..." or "Classify this feedback according to the provided schema...".
- **Validation:**While structured output guarantees syntactically correct JSON, it does not guarantee the values are semantically correct. Always validate the final output in your application code before using it.
- **Error handling:**Implement robust error handling in your application to gracefully manage cases where the model's output, while schema-compliant, may not meet your business logic requirements.

## Limitations

- **Schema subset:**Not all features of the JSON Schema specification are supported. The model ignores unsupported properties.
- **Schema complexity:**The API may reject very large or deeply nested schemas. If you encounter errors, try simplifying your schema by shortening property names, reducing nesting, or limiting the number of constraints.<br />

Function calling lets you connect models to external tools and APIs. Instead of generating text responses, the model determines when to call specific functions and provides the necessary parameters to execute real-world actions. This allows the model to act as a bridge between natural language and real-world actions and data. Function calling has 3 primary use cases:

- **Augment Knowledge:**Access information from external sources like databases, APIs, and knowledge bases.
- **Extend Capabilities:**Use external tools to perform computations and extend the limitations of the model, such as using a calculator or creating charts.
- **Take Actions:**Interact with external systems using APIs, such as scheduling appointments, creating invoices, sending emails, or controlling smart home devices.

Get WeatherSchedule MeetingCreate Chart  

### Python

    from google import genai
    from google.genai import types

    # Define the function declaration for the model
    schedule_meeting_function = {
        "name": "schedule_meeting",
        "description": "Schedules a meeting with specified attendees at a given time and date.",
        "parameters": {
            "type": "object",
            "properties": {
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of people attending the meeting.",
                },
                "date": {
                    "type": "string",
                    "description": "Date of the meeting (e.g., '2024-07-29')",
                },
                "time": {
                    "type": "string",
                    "description": "Time of the meeting (e.g., '15:00')",
                },
                "topic": {
                    "type": "string",
                    "description": "The subject or topic of the meeting.",
                },
            },
            "required": ["attendees", "date", "time", "topic"],
        },
    }

    # Configure the client and tools
    client = genai.Client()
    tools = types.Tool(function_declarations=[schedule_meeting_function])
    config = types.GenerateContentConfig(tools=[tools])

    # Send request with function declarations
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Schedule a meeting with Bob and Alice for 03/14/2025 at 10:00 AM about the Q3 planning.",
        config=config,
    )

    # Check for a function call
    if response.candidates[0].content.parts[0].function_call:
        function_call = response.candidates[0].content.parts[0].function_call
        print(f"Function to call: {function_call.name}")
        print(f"Arguments: {function_call.args}")
        #  In a real app, you would call your function here:
        #  result = schedule_meeting(**function_call.args)
    else:
        print("No function call found in the response.")
        print(response.text)

### JavaScript

    import { GoogleGenAI, Type } from '@google/genai';

    // Configure the client
    const ai = new GoogleGenAI({});

    // Define the function declaration for the model
    const scheduleMeetingFunctionDeclaration = {
      name: 'schedule_meeting',
      description: 'Schedules a meeting with specified attendees at a given time and date.',
      parameters: {
        type: Type.OBJECT,
        properties: {
          attendees: {
            type: Type.ARRAY,
            items: { type: Type.STRING },
            description: 'List of people attending the meeting.',
          },
          date: {
            type: Type.STRING,
            description: 'Date of the meeting (e.g., "2024-07-29")',
          },
          time: {
            type: Type.STRING,
            description: 'Time of the meeting (e.g., "15:00")',
          },
          topic: {
            type: Type.STRING,
            description: 'The subject or topic of the meeting.',
          },
        },
        required: ['attendees', 'date', 'time', 'topic'],
      },
    };

    // Send request with function declarations
    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: 'Schedule a meeting with Bob and Alice for 03/27/2025 at 10:00 AM about the Q3 planning.',
      config: {
        tools: [{
          functionDeclarations: [scheduleMeetingFunctionDeclaration]
        }],
      },
    });

    // Check for function calls in the response
    if (response.functionCalls && response.functionCalls.length > 0) {
      const functionCall = response.functionCalls[0]; // Assuming one function call
      console.log(`Function to call: ${functionCall.name}`);
      console.log(`Arguments: ${JSON.stringify(functionCall.args)}`);
      // In a real app, you would call your actual function here:
      // const result = await scheduleMeeting(functionCall.args);
    } else {
      console.log("No function call found in the response.");
      console.log(response.text);
    }

### REST

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" \
      -H "x-goog-api-key: $GEMINI_API_KEY" \
      -H 'Content-Type: application/json' \
      -X POST \
      -d '{
        "contents": [
          {
            "role": "user",
            "parts": [
              {
                "text": "Schedule a meeting with Bob and Alice for 03/27/2025 at 10:00 AM about the Q3 planning."
              }
            ]
          }
        ],
        "tools": [
          {
            "functionDeclarations": [
              {
                "name": "schedule_meeting",
                "description": "Schedules a meeting with specified attendees at a given time and date.",
                "parameters": {
                  "type": "object",
                  "properties": {
                    "attendees": {
                      "type": "array",
                      "items": {"type": "string"},
                      "description": "List of people attending the meeting."
                    },
                    "date": {
                      "type": "string",
                      "description": "Date of the meeting (e.g., '2024-07-29')"
                    },
                    "time": {
                      "type": "string",
                      "description": "Time of the meeting (e.g., '15:00')"
                    },
                    "topic": {
                      "type": "string",
                      "description": "The subject or topic of the meeting."
                    }
                  },
                  "required": ["attendees", "date", "time", "topic"]
                }
              }
            ]
          }
        ]
      }'

## How function calling works

![function calling overview](https://ai.google.dev/static/gemini-api/docs/images/function-calling-overview.png)

Function calling involves a structured interaction between your application, the model, and external functions. Here's a breakdown of the process:

1. **Define Function Declaration:**Define the function declaration in your application code. Function Declarations describe the function's name, parameters, and purpose to the model.
2. **Call LLM with function declarations:**Send user prompt along with the function declaration(s) to the model. It analyzes the request and determines if a function call would be helpful. If so, it responds with a structured JSON object.
3. **Execute Function Code (Your Responsibility):** The Model*does not* execute the function itself. It's your application's responsibility to process the response and check for Function Call, if
   - **Yes**: Extract the name and args of the function and execute the corresponding function in your application.
   - **No:**The model has provided a direct text response to the prompt (this flow is less emphasized in the example but is a possible outcome).
4. **Create User friendly response:**If a function was executed, capture the result and send it back to the model in a subsequent turn of the conversation. It will use the result to generate a final, user-friendly response that incorporates the information from the function call.

This process can be repeated over multiple turns, allowing for complex interactions and workflows. The model also supports calling multiple functions in a single turn ([parallel function calling](https://ai.google.dev/gemini-api/docs/function-calling#parallel_function_calling)) and in sequence ([compositional function calling](https://ai.google.dev/gemini-api/docs/function-calling#compositional_function_calling)).

### Step 1: Define a function declaration

Define a function and its declaration within your application code that allows users to set light values and make an API request. This function could call external services or APIs.  

### Python

    # Define a function that the model can call to control smart lights
    set_light_values_declaration = {
        "name": "set_light_values",
        "description": "Sets the brightness and color temperature of a light.",
        "parameters": {
            "type": "object",
            "properties": {
                "brightness": {
                    "type": "integer",
                    "description": "Light level from 0 to 100. Zero is off and 100 is full brightness",
                },
                "color_temp": {
                    "type": "string",
                    "enum": ["daylight", "cool", "warm"],
                    "description": "Color temperature of the light fixture, which can be `daylight`, `cool` or `warm`.",
                },
            },
            "required": ["brightness", "color_temp"],
        },
    }

    # This is the actual function that would be called based on the model's suggestion
    def set_light_values(brightness: int, color_temp: str) -> dict[str, int | str]:
        """Set the brightness and color temperature of a room light. (mock API).

        Args:
            brightness: Light level from 0 to 100. Zero is off and 100 is full brightness
            color_temp: Color temperature of the light fixture, which can be `daylight`, `cool` or `warm`.

        Returns:
            A dictionary containing the set brightness and color temperature.
        """
        return {"brightness": brightness, "colorTemperature": color_temp}

### JavaScript

    import { Type } from '@google/genai';

    // Define a function that the model can call to control smart lights
    const setLightValuesFunctionDeclaration = {
      name: 'set_light_values',
      description: 'Sets the brightness and color temperature of a light.',
      parameters: {
        type: Type.OBJECT,
        properties: {
          brightness: {
            type: Type.NUMBER,
            description: 'Light level from 0 to 100. Zero is off and 100 is full brightness',
          },
          color_temp: {
            type: Type.STRING,
            enum: ['daylight', 'cool', 'warm'],
            description: 'Color temperature of the light fixture, which can be `daylight`, `cool` or `warm`.',
          },
        },
        required: ['brightness', 'color_temp'],
      },
    };

    /**

    *   Set the brightness and color temperature of a room light. (mock API)
    *   @param {number} brightness - Light level from 0 to 100. Zero is off and 100 is full brightness
    *   @param {string} color_temp - Color temperature of the light fixture, which can be `daylight`, `cool` or `warm`.
    *   @return {Object} A dictionary containing the set brightness and color temperature.
    */
    function setLightValues(brightness, color_temp) {
      return {
        brightness: brightness,
        colorTemperature: color_temp
      };
    }

### Step 2: Call the model with function declarations

Once you have defined your function declarations, you can prompt the model to use them. It analyzes the prompt and function declarations and decides whether to respond directly or to call a function. If a function is called, the response object will contain a function call suggestion.  

### Python

    from google.genai import types

    # Configure the client and tools
    client = genai.Client()
    tools = types.Tool(function_declarations=[set_light_values_declaration])
    config = types.GenerateContentConfig(tools=[tools])

    # Define user prompt
    contents = [
        types.Content(
            role="user", parts=[types.Part(text="Turn the lights down to a romantic level")]
        )
    ]

    # Send request with function declarations
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents
        config=config,
    )

    print(response.candidates[0].content.parts[0].function_call)

### JavaScript

    import { GoogleGenAI } from '@google/genai';

    // Generation config with function declaration
    const config = {
      tools: [{
        functionDeclarations: [setLightValuesFunctionDeclaration]
      }]
    };

    // Configure the client
    const ai = new GoogleGenAI({});

    // Define user prompt
    const contents = [
      {
        role: 'user',
        parts: [{ text: 'Turn the lights down to a romantic level' }]
      }
    ];

    // Send request with function declarations
    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: contents,
      config: config
    });

    console.log(response.functionCalls[0]);

The model then returns a`functionCall`object in an OpenAPI compatible schema specifying how to call one or more of the declared functions in order to respond to the user's question.  

### Python

    id=None args={'color_temp': 'warm', 'brightness': 25} name='set_light_values'

### JavaScript

    {
      name: 'set_light_values',
      args: { brightness: 25, color_temp: 'warm' }
    }

### Step 3: Execute set_light_values function code

Extract the function call details from the model's response, parse the arguments , and execute the`set_light_values`function.  

### Python

    # Extract tool call details, it may not be in the first part.
    tool_call = response.candidates[0].content.parts[0].function_call

    if tool_call.name == "set_light_values":
        result = set_light_values(**tool_call.args)
        print(f"Function execution result: {result}")

### JavaScript

    // Extract tool call details
    const tool_call = response.functionCalls[0]

    let result;
    if (tool_call.name === 'set_light_values') {
      result = setLightValues(tool_call.args.brightness, tool_call.args.color_temp);
      console.log(`Function execution result: ${JSON.stringify(result)}`);
    }

### Step 4: Create user friendly response with function result and call the model again

Finally, send the result of the function execution back to the model so it can incorporate this information into its final response to the user.  

### Python

    from google import genai
    from google.genai import types

    # Create a function response part
    function_response_part = types.Part.from_function_response(
        name=tool_call.name,
        response={"result": result},
    )

    # Append function call and result of the function execution to contents
    contents.append(response.candidates[0].content) # Append the content from the model's response.
    contents.append(types.Content(role="user", parts=[function_response_part])) # Append the function response

    client = genai.Client()
    final_response = client.models.generate_content(
        model="gemini-2.5-flash",
        config=config,
        contents=contents,
    )

    print(final_response.text)

### JavaScript

    // Create a function response part
    const function_response_part = {
      name: tool_call.name,
      response: { result }
    }

    // Append function call and result of the function execution to contents
    contents.push(response.candidates[0].content);
    contents.push({ role: 'user', parts: [{ functionResponse: function_response_part }] });

    // Get the final response from the model
    const final_response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: contents,
      config: config
    });

    console.log(final_response.text);

This completes the function calling flow. The model successfully used the`set_light_values`function to perform the request action of the user.

## Function declarations

When you implement function calling in a prompt, you create a`tools`object, which contains one or more`function declarations`. You define functions using JSON, specifically with a[select subset](https://ai.google.dev/api/caching#Schema)of the[OpenAPI schema](https://spec.openapis.org/oas/v3.0.3#schemaw)format. A single function declaration can include the following parameters:

- `name`(string): A unique name for the function (`get_weather_forecast`,`send_email`). Use descriptive names without spaces or special characters (use underscores or camelCase).
- `description`(string): A clear and detailed explanation of the function's purpose and capabilities. This is crucial for the model to understand when to use the function. Be specific and provide examples if helpful ("Finds theaters based on location and optionally movie title which is currently playing in theaters.").
- `parameters`(object): Defines the input parameters the function expects.
  - `type`(string): Specifies the overall data type, such as`object`.
  - `properties`(object): Lists individual parameters, each with:
    - `type`(string): The data type of the parameter, such as`string`,`integer`,`boolean, array`.
    - `description`(string): A description of the parameter's purpose and format. Provide examples and constraints ("The city and state, e.g., 'San Francisco, CA' or a zip code e.g., '95616'.").
    - `enum`(array, optional): If the parameter values are from a fixed set, use "enum" to list the allowed values instead of just describing them in the description. This improves accuracy ("enum": \["daylight", "cool", "warm"\]).
  - `required`(array): An array of strings listing the parameter names that are mandatory for the function to operate.

You can also construct`FunctionDeclarations`from Python functions directly using`types.FunctionDeclaration.from_callable(client=client, callable=your_function)`.

## Function calling with thinking models

Gemini 3 and 2.5 series models use an internal["thinking"](https://ai.google.dev/gemini-api/docs/thinking)process to reason through requests. This significantly improves function calling performance, allowing the model to better determine when to call a function and which parameters to use. Because the Gemini API is stateless, models use[thought signatures](https://ai.google.dev/gemini-api/docs/thought-signatures)to maintain context across multi-turn conversations.

This section covers advanced management of thought signatures and is only necessary if you're manually constructing API requests (e.g., via REST) or manipulating conversation history.

**If you're using the[Google GenAI SDKs](https://ai.google.dev/gemini-api/docs/libraries)(our official libraries), you don't need to manage this process** . The SDKs automatically handle the necessary steps, as shown in the earlier[example](https://ai.google.dev/gemini-api/docs/function-calling#step-4).

### Managing conversation history manually

If you modify the conversation history manually, instead of sending the[complete previous response](https://ai.google.dev/gemini-api/docs/function-calling#step-4)you must correctly handle the`thought_signature`included in the model's turn.

Follow these rules to ensure the model's context is preserved:

- Always send the`thought_signature`back to the model inside its original[`Part`](https://ai.google.dev/api#request-body-structure).
- Don't merge a`Part`containing a signature with one that does not. This breaks the positional context of the thought.
- Don't combine two`Parts`that both contain signatures, as the signature strings cannot be merged.

#### Gemini 3 thought signatures

In Gemini 3, any[`Part`](https://ai.google.dev/api#request-body-structure)of a model response may contain a thought signature. While we generally recommend returning signatures from all`Part`types, passing back thought signatures is mandatory for function calling. Unless you are manipulating conversation history manually, the Google GenAI SDK will handle thought signatures automatically.

If you are manipulating conversation history manually, refer to the[Thoughts Signatures](https://ai.google.dev/gemini-api/docs/thought-signatures)page for complete guidance and details on handling thought signatures for Gemini 3.

### Inspecting thought signatures

While not necessary for implementation, you can inspect the response to see the`thought_signature`for debugging or educational purposes.  

### Python

    import base64
    # After receiving a response from a model with thinking enabled
    # response = client.models.generate_content(...)

    # The signature is attached to the response part containing the function call
    part = response.candidates[0].content.parts[0]
    if part.thought_signature:
      print(base64.b64encode(part.thought_signature).decode("utf-8"))

### JavaScript

    // After receiving a response from a model with thinking enabled
    // const response = await ai.models.generateContent(...)

    // The signature is attached to the response part containing the function call
    const part = response.candidates[0].content.parts[0];
    if (part.thoughtSignature) {
      console.log(part.thoughtSignature);
    }

Learn more about limitations and usage of thought signatures, and about thinking models in general, on the[Thinking](https://ai.google.dev/gemini-api/docs/thinking#signatures)page.

## Parallel function calling

In addition to single turn function calling, you can also call multiple functions at once. Parallel function calling lets you execute multiple functions at once and is used when the functions are not dependent on each other. This is useful in scenarios like gathering data from multiple independent sources, such as retrieving customer details from different databases or checking inventory levels across various warehouses or performing multiple actions such as converting your apartment into a disco.  

### Python

    power_disco_ball = {
        "name": "power_disco_ball",
        "description": "Powers the spinning disco ball.",
        "parameters": {
            "type": "object",
            "properties": {
                "power": {
                    "type": "boolean",
                    "description": "Whether to turn the disco ball on or off.",
                }
            },
            "required": ["power"],
        },
    }

    start_music = {
        "name": "start_music",
        "description": "Play some music matching the specified parameters.",
        "parameters": {
            "type": "object",
            "properties": {
                "energetic": {
                    "type": "boolean",
                    "description": "Whether the music is energetic or not.",
                },
                "loud": {
                    "type": "boolean",
                    "description": "Whether the music is loud or not.",
                },
            },
            "required": ["energetic", "loud"],
        },
    }

    dim_lights = {
        "name": "dim_lights",
        "description": "Dim the lights.",
        "parameters": {
            "type": "object",
            "properties": {
                "brightness": {
                    "type": "number",
                    "description": "The brightness of the lights, 0.0 is off, 1.0 is full.",
                }
            },
            "required": ["brightness"],
        },
    }

### JavaScript

    import { Type } from '@google/genai';

    const powerDiscoBall = {
      name: 'power_disco_ball',
      description: 'Powers the spinning disco ball.',
      parameters: {
        type: Type.OBJECT,
        properties: {
          power: {
            type: Type.BOOLEAN,
            description: 'Whether to turn the disco ball on or off.'
          }
        },
        required: ['power']
      }
    };

    const startMusic = {
      name: 'start_music',
      description: 'Play some music matching the specified parameters.',
      parameters: {
        type: Type.OBJECT,
        properties: {
          energetic: {
            type: Type.BOOLEAN,
            description: 'Whether the music is energetic or not.'
          },
          loud: {
            type: Type.BOOLEAN,
            description: 'Whether the music is loud or not.'
          }
        },
        required: ['energetic', 'loud']
      }
    };

    const dimLights = {
      name: 'dim_lights',
      description: 'Dim the lights.',
      parameters: {
        type: Type.OBJECT,
        properties: {
          brightness: {
            type: Type.NUMBER,
            description: 'The brightness of the lights, 0.0 is off, 1.0 is full.'
          }
        },
        required: ['brightness']
      }
    };

Configure the function calling mode to allow using all of the specified tools. To learn more, you can read about[configuring function calling](https://ai.google.dev/gemini-api/docs/function-calling#function_calling_modes).  

### Python

    from google import genai
    from google.genai import types

    # Configure the client and tools
    client = genai.Client()
    house_tools = [
        types.Tool(function_declarations=[power_disco_ball, start_music, dim_lights])
    ]
    config = types.GenerateContentConfig(
        tools=house_tools,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True
        ),
        # Force the model to call 'any' function, instead of chatting.
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode='ANY')
        ),
    )

    chat = client.chats.create(model="gemini-2.5-flash", config=config)
    response = chat.send_message("Turn this place into a party!")

    # Print out each of the function calls requested from this single call
    print("Example 1: Forced function calling")
    for fn in response.function_calls:
        args = ", ".join(f"{key}={val}" for key, val in fn.args.items())
        print(f"{fn.name}({args})")

### JavaScript

    import { GoogleGenAI } from '@google/genai';

    // Set up function declarations
    const houseFns = [powerDiscoBall, startMusic, dimLights];

    const config = {
        tools: [{
            functionDeclarations: houseFns
        }],
        // Force the model to call 'any' function, instead of chatting.
        toolConfig: {
            functionCallingConfig: {
                mode: 'any'
            }
        }
    };

    // Configure the client
    const ai = new GoogleGenAI({});

    // Create a chat session
    const chat = ai.chats.create({
        model: 'gemini-2.5-flash',
        config: config
    });
    const response = await chat.sendMessage({message: 'Turn this place into a party!'});

    // Print out each of the function calls requested from this single call
    console.log("Example 1: Forced function calling");
    for (const fn of response.functionCalls) {
        const args = Object.entries(fn.args)
            .map(([key, val]) => `${key}=${val}`)
            .join(', ');
        console.log(`${fn.name}(${args})`);
    }

Each of the printed results reflects a single function call that the model has requested. To send the results back, include the responses in the same order as they were requested.

The Python SDK supports[automatic function calling](https://ai.google.dev/gemini-api/docs/function-calling#automatic_function_calling_python_only), which automatically converts Python functions to declarations, handles the function call execution and response cycle for you. Following is an example for the disco use case.
**Note:** Automatic Function Calling is a Python SDK only feature at the moment.  

### Python

    from google import genai
    from google.genai import types

    # Actual function implementations
    def power_disco_ball_impl(power: bool) -> dict:
        """Powers the spinning disco ball.

        Args:
            power: Whether to turn the disco ball on or off.

        Returns:
            A status dictionary indicating the current state.
        """
        return {"status": f"Disco ball powered {'on' if power else 'off'}"}

    def start_music_impl(energetic: bool, loud: bool) -> dict:
        """Play some music matching the specified parameters.

        Args:
            energetic: Whether the music is energetic or not.
            loud: Whether the music is loud or not.

        Returns:
            A dictionary containing the music settings.
        """
        music_type = "energetic" if energetic else "chill"
        volume = "loud" if loud else "quiet"
        return {"music_type": music_type, "volume": volume}

    def dim_lights_impl(brightness: float) -> dict:
        """Dim the lights.

        Args:
            brightness: The brightness of the lights, 0.0 is off, 1.0 is full.

        Returns:
            A dictionary containing the new brightness setting.
        """
        return {"brightness": brightness}

    # Configure the client
    client = genai.Client()
    config = types.GenerateContentConfig(
        tools=[power_disco_ball_impl, start_music_impl, dim_lights_impl]
    )

    # Make the request
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Do everything you need to this place into party!",
        config=config,
    )

    print("\nExample 2: Automatic function calling")
    print(response.text)
    # I've turned on the disco ball, started playing loud and energetic music, and dimmed the lights to 50% brightness. Let's get this party started!

## Compositional function calling

Compositional or sequential function calling allows Gemini to chain multiple function calls together to fulfill a complex request. For example, to answer "Get the temperature in my current location", the Gemini API might first invoke a`get_current_location()`function followed by a`get_weather()`function that takes the location as a parameter.

The following example demonstrates how to implement compositional function calling using the Python SDK and automatic function calling.  

### Python

This example uses the automatic function calling feature of the`google-genai`Python SDK. The SDK automatically converts the Python functions to the required schema, executes the function calls when requested by the model, and sends the results back to the model to complete the task.  

    import os
    from google import genai
    from google.genai import types

    # Example Functions
    def get_weather_forecast(location: str) -> dict:
        """Gets the current weather temperature for a given location."""
        print(f"Tool Call: get_weather_forecast(location={location})")
        # TODO: Make API call
        print("Tool Response: {'temperature': 25, 'unit': 'celsius'}")
        return {"temperature": 25, "unit": "celsius"}  # Dummy response

    def set_thermostat_temperature(temperature: int) -> dict:
        """Sets the thermostat to a desired temperature."""
        print(f"Tool Call: set_thermostat_temperature(temperature={temperature})")
        # TODO: Interact with a thermostat API
        print("Tool Response: {'status': 'success'}")
        return {"status": "success"}

    # Configure the client and model
    client = genai.Client()
    config = types.GenerateContentConfig(
        tools=[get_weather_forecast, set_thermostat_temperature]
    )

    # Make the request
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="If it's warmer than 20°C in London, set the thermostat to 20°C, otherwise set it to 18°C.",
        config=config,
    )

    # Print the final, user-facing response
    print(response.text)

**Expected Output**

When you run the code, you will see the SDK orchestrating the function calls. The model first calls`get_weather_forecast`, receives the temperature, and then calls`set_thermostat_temperature`with the correct value based on the logic in the prompt.  

    Tool Call: get_weather_forecast(location=London)
    Tool Response: {'temperature': 25, 'unit': 'celsius'}
    Tool Call: set_thermostat_temperature(temperature=20)
    Tool Response: {'status': 'success'}
    OK. I've set the thermostat to 20°C.

### JavaScript

This example shows how to use JavaScript/TypeScript SDK to do comopositional function calling using a manual execution loop.  

    import { GoogleGenAI, Type } from "@google/genai";

    // Configure the client
    const ai = new GoogleGenAI({});

    // Example Functions
    function get_weather_forecast({ location }) {
      console.log(`Tool Call: get_weather_forecast(location=${location})`);
      // TODO: Make API call
      console.log("Tool Response: {'temperature': 25, 'unit': 'celsius'}");
      return { temperature: 25, unit: "celsius" };
    }

    function set_thermostat_temperature({ temperature }) {
      console.log(
        `Tool Call: set_thermostat_temperature(temperature=${temperature})`,
      );
      // TODO: Make API call
      console.log("Tool Response: {'status': 'success'}");
      return { status: "success" };
    }

    const toolFunctions = {
      get_weather_forecast,
      set_thermostat_temperature,
    };

    const tools = [
      {
        functionDeclarations: [
          {
            name: "get_weather_forecast",
            description:
              "Gets the current weather temperature for a given location.",
            parameters: {
              type: Type.OBJECT,
              properties: {
                location: {
                  type: Type.STRING,
                },
              },
              required: ["location"],
            },
          },
          {
            name: "set_thermostat_temperature",
            description: "Sets the thermostat to a desired temperature.",
            parameters: {
              type: Type.OBJECT,
              properties: {
                temperature: {
                  type: Type.NUMBER,
                },
              },
              required: ["temperature"],
            },
          },
        ],
      },
    ];

    // Prompt for the model
    let contents = [
      {
        role: "user",
        parts: [
          {
            text: "If it's warmer than 20°C in London, set the thermostat to 20°C, otherwise set it to 18°C.",
          },
        ],
      },
    ];

    // Loop until the model has no more function calls to make
    while (true) {
      const result = await ai.models.generateContent({
        model: "gemini-2.5-flash",
        contents,
        config: { tools },
      });

      if (result.functionCalls && result.functionCalls.length > 0) {
        const functionCall = result.functionCalls[0];

        const { name, args } = functionCall;

        if (!toolFunctions[name]) {
          throw new Error(`Unknown function call: ${name}`);
        }

        // Call the function and get the response.
        const toolResponse = toolFunctions[name](args);

        const functionResponsePart = {
          name: functionCall.name,
          response: {
            result: toolResponse,
          },
        };

        // Send the function response back to the model.
        contents.push({
          role: "model",
          parts: [
            {
              functionCall: functionCall,
            },
          ],
        });
        contents.push({
          role: "user",
          parts: [
            {
              functionResponse: functionResponsePart,
            },
          ],
        });
      } else {
        // No more function calls, break the loop.
        console.log(result.text);
        break;
      }
    }

**Expected Output**

When you run the code, you will see the SDK orchestrating the function calls. The model first calls`get_weather_forecast`, receives the temperature, and then calls`set_thermostat_temperature`with the correct value based on the logic in the prompt.  

    Tool Call: get_weather_forecast(location=London)
    Tool Response: {'temperature': 25, 'unit': 'celsius'}
    Tool Call: set_thermostat_temperature(temperature=20)
    Tool Response: {'status': 'success'}
    OK. It's 25°C in London, so I've set the thermostat to 20°C.

Compositional function calling is a native[Live API](https://ai.google.dev/gemini-api/docs/live)feature. This means Live API can handle the function calling similar to the Python SDK.  

### Python

    # Light control schemas
    turn_on_the_lights_schema = {'name': 'turn_on_the_lights'}
    turn_off_the_lights_schema = {'name': 'turn_off_the_lights'}

    prompt = """
      Hey, can you write run some python code to turn on the lights, wait 10s and then turn off the lights?
      """

    tools = [
        {'code_execution': {}},
        {'function_declarations': [turn_on_the_lights_schema, turn_off_the_lights_schema]}
    ]

    await run(prompt, tools=tools, modality="AUDIO")

### JavaScript

    // Light control schemas
    const turnOnTheLightsSchema = { name: 'turn_on_the_lights' };
    const turnOffTheLightsSchema = { name: 'turn_off_the_lights' };

    const prompt = `
      Hey, can you write run some python code to turn on the lights, wait 10s and then turn off the lights?
    `;

    const tools = [
      { codeExecution: {} },
      { functionDeclarations: [turnOnTheLightsSchema, turnOffTheLightsSchema] }
    ];

    await run(prompt, tools=tools, modality="AUDIO")

## Function calling modes

The Gemini API lets you control how the model uses the provided tools (function declarations). Specifically, you can set the mode within the.`function_calling_config`.

- `AUTO (Default)`: The model decides whether to generate a natural language response or suggest a function call based on the prompt and context. This is the most flexible mode and recommended for most scenarios.
- `ANY`: The model is constrained to always predict a function call and guarantees function schema adherence. If`allowed_function_names`is not specified, the model can choose from any of the provided function declarations. If`allowed_function_names`is provided as a list, the model can only choose from the functions in that list. Use this mode when you require a function call response to every prompt (if applicable).
- `NONE`: The model is*prohibited*from making function calls. This is equivalent to sending a request without any function declarations. Use this to temporarily disable function calling without removing your tool definitions.
- `VALIDATED`(Preview): The model is constrained to predict either function calls or natural language, and ensures function schema adherence. If`allowed_function_names`is not provided, the model picks from all of the available function declarations. If`allowed_function_names`is provided, the model picks from the set of allowed functions.

### Python

    from google.genai import types

    # Configure function calling mode
    tool_config = types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(
            mode="ANY", allowed_function_names=["get_current_temperature"]
        )
    )

    # Create the generation config
    config = types.GenerateContentConfig(
        tools=[tools],  # not defined here.
        tool_config=tool_config,
    )

### JavaScript

    import { FunctionCallingConfigMode } from '@google/genai';

    // Configure function calling mode
    const toolConfig = {
      functionCallingConfig: {
        mode: FunctionCallingConfigMode.ANY,
        allowedFunctionNames: ['get_current_temperature']
      }
    };

    // Create the generation config
    const config = {
      tools: tools, // not defined here.
      toolConfig: toolConfig,
    };

## Automatic function calling (Python only)

When using the Python SDK, you can provide Python functions directly as tools. The SDK converts these functions into declarations, manages the function call execution, and handles the response cycle for you. Define your function with type hints and a docstring. For optimal results, it is recommended to use[Google-style docstrings.](https://google.github.io/styleguide/pyguide.html#383-functions-and-methods)The SDK will then automatically:

1. Detect function call responses from the model.
2. Call the corresponding Python function in your code.
3. Send the function's response back to the model.
4. Return the model's final text response.

The SDK currently does not parse argument descriptions into the property description slots of the generated function declaration. Instead, it sends the entire docstring as the top-level function description.  

### Python

    from google import genai
    from google.genai import types

    # Define the function with type hints and docstring
    def get_current_temperature(location: str) -> dict:
        """Gets the current temperature for a given location.

        Args:
            location: The city and state, e.g. San Francisco, CA

        Returns:
            A dictionary containing the temperature and unit.
        """
        # ... (implementation) ...
        return {"temperature": 25, "unit": "Celsius"}

    # Configure the client
    client = genai.Client()
    config = types.GenerateContentConfig(
        tools=[get_current_temperature]
    )  # Pass the function itself

    # Make the request
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="What's the temperature in Boston?",
        config=config,
    )

    print(response.text)  # The SDK handles the function call and returns the final text

You can disable automatic function calling with:  

### Python

    config = types.GenerateContentConfig(
        tools=[get_current_temperature],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
    )

### Automatic function schema declaration

The API is able to describe any of the following types.`Pydantic`types are allowed, as long as the fields defined on them are also composed of allowed types. Dict types (like`dict[str: int]`) are not well supported here, don't use them.  

### Python

    AllowedType = (
      int | float | bool | str | list['AllowedType'] | pydantic.BaseModel)

To see what the inferred schema looks like, you can convert it using[`from_callable`](https://googleapis.github.io/python-genai/genai.html#genai.types.FunctionDeclaration.from_callable):  

### Python

    from google import genai
    from google.genai import types

    def multiply(a: float, b: float):
        """Returns a * b."""
        return a * b

    client = genai.Client()
    fn_decl = types.FunctionDeclaration.from_callable(callable=multiply, client=client)

    # to_json_dict() provides a clean JSON representation.
    print(fn_decl.to_json_dict())

## Multi-tool use: Combine native tools with function calling

You can enable multiple tools combining native tools with function calling at the same time. Here's an example that enables two tools,[Grounding with Google Search](https://ai.google.dev/gemini-api/docs/grounding)and[code execution](https://ai.google.dev/gemini-api/docs/code-execution), in a request using the[Live API](https://ai.google.dev/gemini-api/docs/live).
**Note:** Multi-tool use is a-[Live API](https://ai.google.dev/gemini-api/docs/live)only feature at the moment. The`run()`function declaration, which handles the asynchronous websocket setup, is omitted for brevity.  

### Python

    # Multiple tasks example - combining lights, code execution, and search
    prompt = """
      Hey, I need you to do three things for me.

        1.  Turn on the lights.
        2.  Then compute the largest prime palindrome under 100000.
        3.  Then use Google Search to look up information about the largest earthquake in California the week of Dec 5 2024.

      Thanks!
      """

    tools = [
        {'google_search': {}},
        {'code_execution': {}},
        {'function_declarations': [turn_on_the_lights_schema, turn_off_the_lights_schema]} # not defined here.
    ]

    # Execute the prompt with specified tools in audio modality
    await run(prompt, tools=tools, modality="AUDIO")

### JavaScript

    // Multiple tasks example - combining lights, code execution, and search
    const prompt = `
      Hey, I need you to do three things for me.

        1.  Turn on the lights.
        2.  Then compute the largest prime palindrome under 100000.
        3.  Then use Google Search to look up information about the largest earthquake in California the week of Dec 5 2024.

      Thanks!
    `;

    const tools = [
      { googleSearch: {} },
      { codeExecution: {} },
      { functionDeclarations: [turnOnTheLightsSchema, turnOffTheLightsSchema] } // not defined here.
    ];

    // Execute the prompt with specified tools in audio modality
    await run(prompt, {tools: tools, modality: "AUDIO"});

Python developers can try this out in the[Live API Tool Use notebook](https://colab.research.google.com/github/google-gemini/cookbook/blob/main/quickstarts/Get_started_LiveAPI_tools.ipynb).

## Multimodal function responses

| **Note:** This feature is available for[Gemini 3](https://ai.google.dev/gemini-api/docs/gemini-3)series models.

For Gemini 3 series models, you can include multimodal content in the function response parts that you send to the model. The model can process this multimodal content in its next turn to produce a more informed response. The following MIME types are supported for multimodal content in function responses:

- **Images** :`image/png`,`image/jpeg`,`image/webp`
- **Documents** :`application/pdf`,`text/plain`

To include multimodal data in a function response, include it as one or more parts nested within the`functionResponse`part. Each multimodal part must contain`inlineData`. If you reference a multimodal part from within the structured`response`field, it must contain a unique`displayName`.

You can also reference a multimodal part from within the structured`response`field of the`functionResponse`part by using the JSON reference format`{"$ref": "<displayName>"}`. The model substitutes the reference with the multimodal content when processing the response. Each`displayName`can only be referenced once in the structured`response`field.

The following example shows a message containing a`functionResponse`for a function named`get_image`and a nested part containing image data with`displayName: "wakeupcat.jpg"`. The`functionResponse`'s`response`field references this image part:  

### Python

    from google import genai
    from google.genai import types

    client = genai.Client()

    # This is a manual, two turn multimodal function calling workflow:

    # 1. Define the function tool
    get_image_declaration = types.FunctionDeclaration(
      name="get_image",
      description="Retrieves the image file reference for a specific order item.",
      parameters={
          "type": "object",
          "properties": {
              "item_name": {
                  "type": "string",
                  "description": "The name or description of the item ordered (e.g., 'green shirt')."
              }
          },
          "required": ["item_name"],
      },
    )
    tool_config = types.Tool(function_declarations=[get_image_declaration])

    # 2. Send a message that triggers the tool
    prompt = "Show me the green shirt I ordered last month."
    response_1 = client.models.generate_content(
      model="gemini-3-flash-preview",
      contents=[prompt],
      config=types.GenerateContentConfig(
          tools=[tool_config],
      )
    )

    # 3. Handle the function call
    function_call = response_1.function_calls[0]
    requested_item = function_call.args["item_name"]
    print(f"Model wants to call: {function_call.name}")

    # Execute your tool (e.g., call an API)
    # (This is a mock response for the example)
    print(f"Calling external tool for: {requested_item}")

    function_response_data = {
      "image_ref": {"$ref": "dress.jpg"},
    }

    function_response_multimodal_data = types.FunctionResponsePart(
      file_data=types.FunctionResponseFileData(
        mime_type="image/png",
        display_name="dress.jpg",
        file_uri="gs://cloud-samples-data/generative-ai/image/dress.jpg",
      )
    )

    # 4. Send the tool's result back
    # Append this turn's messages to history for a final response.
    history = [
      types.Content(role="user", parts=[types.Part(text=prompt)]),
      response_1.candidates[0].content,
      types.Content(
        role="tool",
        parts=[
            types.Part.from_function_response(
              name=function_call.name,
              response=function_response_data,
              parts=[function_response_multimodal_data]
            )
        ],
      )
    ]

    response_2 = client.models.generate_content(
      model="gemini-3-flash-preview",
      contents=history,
      config=types.GenerateContentConfig(
          tools=[tool_config],
          thinking_config=types.ThinkingConfig(include_thoughts=True)
      ),
    )

    print(f"\nFinal model response: {response_2.text}")

### JavaScript

    import { GoogleGenAI, Type } from '@google/genai';

    const client = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

    // This is a manual, two turn multimodal function calling workflow:
    // 1. Define the function tool
    const getImageDeclaration = {
      name: 'get_image',
      description: 'Retrieves the image file reference for a specific order item.',
      parameters: {
        type: Type.OBJECT,
        properties: {
          item_name: {
            type: Type.STRING,
            description: "The name or description of the item ordered (e.g., 'green shirt').",
          },
        },
        required: ['item_name'],
      },
    };

    const toolConfig = {
      functionDeclarations: [getImageDeclaration],
    };

    // 2. Send a message that triggers the tool
    const prompt = 'Show me the green shirt I ordered last month.';
    const response1 = await client.models.generateContent({
      model: 'gemini-3-flash-preview',
      contents: prompt,
      config: {
        tools: [toolConfig],
      },
    });

    // 3. Handle the function call
    const functionCall = response1.functionCalls[0];
    const requestedItem = functionCall.args.item_name;
    console.log(`Model wants to call: ${functionCall.name}`);

    // Execute your tool (e.g., call an API)
    // (This is a mock response for the example)
    console.log(`Calling external tool for: ${requestedItem}`);

    const functionResponseData = {
      image_ref: { $ref: 'dress.jpg' },
    };

    const functionResponseMultimodalData = {
      fileData: {
        mimeType: 'image/png',
        displayName: 'dress.jpg',
        fileUri: 'gs://cloud-samples-data/generative-ai/image/dress.jpg',
      },
    };

    // 4. Send the tool's result back
    // Append this turn's messages to history for a final response.
    const history = [
      { role: 'user', parts: [{ text: prompt }] },
      response1.candidates[0].content,
      {
        role: 'tool',
        parts: [
          {
            functionResponse: {
              name: functionCall.name,
              response: functionResponseData,
              parts: [functionResponseMultimodalData],
            },
          },
        ],
      },
    ];

    const response2 = await client.models.generateContent({
      model: 'gemini-3-flash-preview',
      contents: history,
      config: {
        tools: [toolConfig],
        thinkingConfig: { includeThoughts: true },
      },
    });

    console.log(`\nFinal model response: ${response2.text}`);

### REST

    "contents": [
      ...,
      {
        "role": "user",
        "parts": [
          {
            "functionResponse": {
              "name": "get_image",
              "response": {
                "image_ref": {
                  "$ref": "wakeupcat.jpg"
                }
              },
              "parts": [
                {
                  "fileData": {
                    "displayName": "wakeupcat.jpg",
                    "mimeType": "image/jpeg",
                    "fileUri": "gs://cloud-samples-data/vision/label/wakeupcat.jpg"
                  }
                }
              ]
            }
          }
        ]
      }
    ]

## Model context protocol (MCP)

[Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction)is an open standard for connecting AI applications with external tools and data. MCP provides a common protocol for models to access context, such as functions (tools), data sources (resources), or predefined prompts.

The Gemini SDKs have built-in support for the MCP, reducing boilerplate code and offering[automatic tool calling](https://ai.google.dev/gemini-api/docs/function-calling#automatic_function_calling_python_only)for MCP tools. When the model generates an MCP tool call, the Python and JavaScript client SDK can automatically execute the MCP tool and send the response back to the model in a subsequent request, continuing this loop until no more tool calls are made by the model.

Here, you can find an example of how to use a local MCP server with Gemini and`mcp`SDK.  

### Python

Make sure the latest version of the[`mcp`SDK](https://modelcontextprotocol.io/introduction)is installed on your platform of choice.  

    pip install mcp

**Note:** Python supports automatic tool calling by passing in the`ClientSession`into the`tools`parameters. If you want to disable it, you can provide`automatic_function_calling`with disabled`True`.  

    import os
    import asyncio
    from datetime import datetime
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from google import genai

    client = genai.Client()

    # Create server parameters for stdio connection
    server_params = StdioServerParameters(
        command="npx",  # Executable
        args=["-y", "@philschmid/weather-mcp"],  # MCP Server
        env=None,  # Optional environment variables
    )

    async def run():
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Prompt to get the weather for the current day in London.
                prompt = f"What is the weather in London in {datetime.now().strftime('%Y-%m-%d')}?"

                # Initialize the connection between client and server
                await session.initialize()

                # Send request to the model with MCP function declarations
                response = await client.aio.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        temperature=0,
                        tools=[session],  # uses the session, will automatically call the tool
                        # Uncomment if you **don't** want the SDK to automatically call the tool
                        # automatic_function_calling=genai.types.AutomaticFunctionCallingConfig(
                        #     disable=True
                        # ),
                    ),
                )
                print(response.text)

    # Start the asyncio event loop and run the main function
    asyncio.run(run())

### JavaScript

Make sure the latest version of the`mcp`SDK is installed on your platform of choice.  

    npm install @modelcontextprotocol/sdk

**Note:** JavaScript supports automatic tool calling by wrapping the`client`with`mcpToTool`. If you want to disable it, you can provide`automaticFunctionCalling`with disabled`true`.  

    import { GoogleGenAI, FunctionCallingConfigMode , mcpToTool} from '@google/genai';
    import { Client } from "@modelcontextprotocol/sdk/client/index.js";
    import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

    // Create server parameters for stdio connection
    const serverParams = new StdioClientTransport({
      command: "npx", // Executable
      args: ["-y", "@philschmid/weather-mcp"] // MCP Server
    });

    const client = new Client(
      {
        name: "example-client",
        version: "1.0.0"
      }
    );

    // Configure the client
    const ai = new GoogleGenAI({});

    // Initialize the connection between client and server
    await client.connect(serverParams);

    // Send request to the model with MCP tools
    const response = await ai.models.generateContent({
      model: "gemini-2.5-flash",
      contents: `What is the weather in London in ${new Date().toLocaleDateString()}?`,
      config: {
        tools: [mcpToTool(client)],  // uses the session, will automatically call the tool
        // Uncomment if you **don't** want the sdk to automatically call the tool
        // automaticFunctionCalling: {
        //   disable: true,
        // },
      },
    });
    console.log(response.text)

    // Close the connection
    await client.close();

### Limitations with built-in MCP support

Built-in MCP support is a[experimental](https://ai.google.dev/gemini-api/docs/models#preview)feature in our SDKs and has the following limitations:

- Only tools are supported, not resources nor prompts
- It is available for the Python and JavaScript/TypeScript SDK.
- Breaking changes might occur in future releases.

Manual integration of MCP servers is always an option if these limit what you're building.

## Supported models

This section lists models and their function calling capabilities. Experimental models are not included. You can find a comprehensive capabilities overview on the[model overview](https://ai.google.dev/gemini-api/docs/models)page.

|         Model         | Function Calling | Parallel Function Calling | Compositional Function Calling |
|-----------------------|------------------|---------------------------|--------------------------------|
| Gemini 3 Pro          | ✔️               | ✔️                        | ✔️                             |
| Gemini 3 Flash        | ✔️               | ✔️                        | ✔️                             |
| Gemini 2.5 Pro        | ✔️               | ✔️                        | ✔️                             |
| Gemini 2.5 Flash      | ✔️               | ✔️                        | ✔️                             |
| Gemini 2.5 Flash-Lite | ✔️               | ✔️                        | ✔️                             |
| Gemini 2.0 Flash      | ✔️               | ✔️                        | ✔️                             |
| Gemini 2.0 Flash-Lite | X                | X                         | X                              |

## Best practices

- **Function and Parameter Descriptions:**Be extremely clear and specific in your descriptions. The model relies on these to choose the correct function and provide appropriate arguments.
- **Naming:**Use descriptive function names (without spaces, periods, or dashes).
- **Strong Typing:**Use specific types (integer, string, enum) for parameters to reduce errors. If a parameter has a limited set of valid values, use an enum.
- **Tool Selection:**While the model can use an arbitrary number of tools, providing too many can increase the risk of selecting an incorrect or suboptimal tool. For best results, aim to provide only the relevant tools for the context or task, ideally keeping the active set to a maximum of 10-20. Consider dynamic tool selection based on conversation context if you have a large total number of tools.
- **Prompt Engineering:**
  - Provide context: Tell the model its role (e.g., "You are a helpful weather assistant.").
  - Give instructions: Specify how and when to use functions (e.g., "Don't guess dates; always use a future date for forecasts.").
  - Encourage clarification: Instruct the model to ask clarifying questions if needed.
  - See[Agentic workflows](https://ai.google.dev/gemini-api/docs/prompting-strategies#agentic-workflows)for further strategies on designing these prompts. Here is an example of a tested[system instruction](https://ai.google.dev/gemini-api/docs/prompting-strategies#agentic-si-template).
- **Temperature:**Use a low temperature (e.g., 0) for more deterministic and reliable function calls.

  | When using Gemini 3 models, we strongly recommend keeping the`temperature`at its default value of 1.0. Changing the temperature (setting it below 1.0) may lead to unexpected behavior, such as looping or degraded performance, particularly in complex mathematical or reasoning tasks.
- **Validation:**If a function call has significant consequences (e.g., placing an order), validate the call with the user before executing it.

- **Check Finish Reason:** Always check the[`finishReason`](https://ai.google.dev/api/generate-content#FinishReason)in the model's response to handle cases where the model failed to generate a valid function call.

- **Error Handling**: Implement robust error handling in your functions to gracefully handle unexpected inputs or API failures. Return informative error messages that the model can use to generate helpful responses to the user.

- **Security:**Be mindful of security when calling external APIs. Use appropriate authentication and authorization mechanisms. Avoid exposing sensitive data in function calls.

- **Token Limits:**Function descriptions and parameters count towards your input token limit. If you're hitting token limits, consider limiting the number of functions or the length of the descriptions, break down complex tasks into smaller, more focused function sets.

## Notes and limitations

- Only a[subset of the OpenAPI schema](https://ai.google.dev/api/caching#FunctionDeclaration)is supported.
- Supported parameter types in Python are limited.
- Automatic function calling is a Python SDK feature only.<br />

Function calling lets you connect models to external tools and APIs. Instead of generating text responses, the model determines when to call specific functions and provides the necessary parameters to execute real-world actions. This allows the model to act as a bridge between natural language and real-world actions and data. Function calling has 3 primary use cases:

- **Augment Knowledge:**Access information from external sources like databases, APIs, and knowledge bases.
- **Extend Capabilities:**Use external tools to perform computations and extend the limitations of the model, such as using a calculator or creating charts.
- **Take Actions:**Interact with external systems using APIs, such as scheduling appointments, creating invoices, sending emails, or controlling smart home devices.

Get WeatherSchedule MeetingCreate Chart  

### Python

    from google import genai
    from google.genai import types

    # Define the function declaration for the model
    schedule_meeting_function = {
        "name": "schedule_meeting",
        "description": "Schedules a meeting with specified attendees at a given time and date.",
        "parameters": {
            "type": "object",
            "properties": {
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of people attending the meeting.",
                },
                "date": {
                    "type": "string",
                    "description": "Date of the meeting (e.g., '2024-07-29')",
                },
                "time": {
                    "type": "string",
                    "description": "Time of the meeting (e.g., '15:00')",
                },
                "topic": {
                    "type": "string",
                    "description": "The subject or topic of the meeting.",
                },
            },
            "required": ["attendees", "date", "time", "topic"],
        },
    }

    # Configure the client and tools
    client = genai.Client()
    tools = types.Tool(function_declarations=[schedule_meeting_function])
    config = types.GenerateContentConfig(tools=[tools])

    # Send request with function declarations
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Schedule a meeting with Bob and Alice for 03/14/2025 at 10:00 AM about the Q3 planning.",
        config=config,
    )

    # Check for a function call
    if response.candidates[0].content.parts[0].function_call:
        function_call = response.candidates[0].content.parts[0].function_call
        print(f"Function to call: {function_call.name}")
        print(f"Arguments: {function_call.args}")
        #  In a real app, you would call your function here:
        #  result = schedule_meeting(**function_call.args)
    else:
        print("No function call found in the response.")
        print(response.text)

### JavaScript

    import { GoogleGenAI, Type } from '@google/genai';

    // Configure the client
    const ai = new GoogleGenAI({});

    // Define the function declaration for the model
    const scheduleMeetingFunctionDeclaration = {
      name: 'schedule_meeting',
      description: 'Schedules a meeting with specified attendees at a given time and date.',
      parameters: {
        type: Type.OBJECT,
        properties: {
          attendees: {
            type: Type.ARRAY,
            items: { type: Type.STRING },
            description: 'List of people attending the meeting.',
          },
          date: {
            type: Type.STRING,
            description: 'Date of the meeting (e.g., "2024-07-29")',
          },
          time: {
            type: Type.STRING,
            description: 'Time of the meeting (e.g., "15:00")',
          },
          topic: {
            type: Type.STRING,
            description: 'The subject or topic of the meeting.',
          },
        },
        required: ['attendees', 'date', 'time', 'topic'],
      },
    };

    // Send request with function declarations
    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: 'Schedule a meeting with Bob and Alice for 03/27/2025 at 10:00 AM about the Q3 planning.',
      config: {
        tools: [{
          functionDeclarations: [scheduleMeetingFunctionDeclaration]
        }],
      },
    });

    // Check for function calls in the response
    if (response.functionCalls && response.functionCalls.length > 0) {
      const functionCall = response.functionCalls[0]; // Assuming one function call
      console.log(`Function to call: ${functionCall.name}`);
      console.log(`Arguments: ${JSON.stringify(functionCall.args)}`);
      // In a real app, you would call your actual function here:
      // const result = await scheduleMeeting(functionCall.args);
    } else {
      console.log("No function call found in the response.");
      console.log(response.text);
    }

### REST

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" \
      -H "x-goog-api-key: $GEMINI_API_KEY" \
      -H 'Content-Type: application/json' \
      -X POST \
      -d '{
        "contents": [
          {
            "role": "user",
            "parts": [
              {
                "text": "Schedule a meeting with Bob and Alice for 03/27/2025 at 10:00 AM about the Q3 planning."
              }
            ]
          }
        ],
        "tools": [
          {
            "functionDeclarations": [
              {
                "name": "schedule_meeting",
                "description": "Schedules a meeting with specified attendees at a given time and date.",
                "parameters": {
                  "type": "object",
                  "properties": {
                    "attendees": {
                      "type": "array",
                      "items": {"type": "string"},
                      "description": "List of people attending the meeting."
                    },
                    "date": {
                      "type": "string",
                      "description": "Date of the meeting (e.g., '2024-07-29')"
                    },
                    "time": {
                      "type": "string",
                      "description": "Time of the meeting (e.g., '15:00')"
                    },
                    "topic": {
                      "type": "string",
                      "description": "The subject or topic of the meeting."
                    }
                  },
                  "required": ["attendees", "date", "time", "topic"]
                }
              }
            ]
          }
        ]
      }'

## How function calling works

![function calling overview](https://ai.google.dev/static/gemini-api/docs/images/function-calling-overview.png)

Function calling involves a structured interaction between your application, the model, and external functions. Here's a breakdown of the process:

1. **Define Function Declaration:**Define the function declaration in your application code. Function Declarations describe the function's name, parameters, and purpose to the model.
2. **Call LLM with function declarations:**Send user prompt along with the function declaration(s) to the model. It analyzes the request and determines if a function call would be helpful. If so, it responds with a structured JSON object.
3. **Execute Function Code (Your Responsibility):** The Model*does not* execute the function itself. It's your application's responsibility to process the response and check for Function Call, if
   - **Yes**: Extract the name and args of the function and execute the corresponding function in your application.
   - **No:**The model has provided a direct text response to the prompt (this flow is less emphasized in the example but is a possible outcome).
4. **Create User friendly response:**If a function was executed, capture the result and send it back to the model in a subsequent turn of the conversation. It will use the result to generate a final, user-friendly response that incorporates the information from the function call.

This process can be repeated over multiple turns, allowing for complex interactions and workflows. The model also supports calling multiple functions in a single turn ([parallel function calling](https://ai.google.dev/gemini-api/docs/function-calling#parallel_function_calling)) and in sequence ([compositional function calling](https://ai.google.dev/gemini-api/docs/function-calling#compositional_function_calling)).

### Step 1: Define a function declaration

Define a function and its declaration within your application code that allows users to set light values and make an API request. This function could call external services or APIs.  

### Python

    # Define a function that the model can call to control smart lights
    set_light_values_declaration = {
        "name": "set_light_values",
        "description": "Sets the brightness and color temperature of a light.",
        "parameters": {
            "type": "object",
            "properties": {
                "brightness": {
                    "type": "integer",
                    "description": "Light level from 0 to 100. Zero is off and 100 is full brightness",
                },
                "color_temp": {
                    "type": "string",
                    "enum": ["daylight", "cool", "warm"],
                    "description": "Color temperature of the light fixture, which can be `daylight`, `cool` or `warm`.",
                },
            },
            "required": ["brightness", "color_temp"],
        },
    }

    # This is the actual function that would be called based on the model's suggestion
    def set_light_values(brightness: int, color_temp: str) -> dict[str, int | str]:
        """Set the brightness and color temperature of a room light. (mock API).

        Args:
            brightness: Light level from 0 to 100. Zero is off and 100 is full brightness
            color_temp: Color temperature of the light fixture, which can be `daylight`, `cool` or `warm`.

        Returns:
            A dictionary containing the set brightness and color temperature.
        """
        return {"brightness": brightness, "colorTemperature": color_temp}

### JavaScript

    import { Type } from '@google/genai';

    // Define a function that the model can call to control smart lights
    const setLightValuesFunctionDeclaration = {
      name: 'set_light_values',
      description: 'Sets the brightness and color temperature of a light.',
      parameters: {
        type: Type.OBJECT,
        properties: {
          brightness: {
            type: Type.NUMBER,
            description: 'Light level from 0 to 100. Zero is off and 100 is full brightness',
          },
          color_temp: {
            type: Type.STRING,
            enum: ['daylight', 'cool', 'warm'],
            description: 'Color temperature of the light fixture, which can be `daylight`, `cool` or `warm`.',
          },
        },
        required: ['brightness', 'color_temp'],
      },
    };

    /**

    *   Set the brightness and color temperature of a room light. (mock API)
    *   @param {number} brightness - Light level from 0 to 100. Zero is off and 100 is full brightness
    *   @param {string} color_temp - Color temperature of the light fixture, which can be `daylight`, `cool` or `warm`.
    *   @return {Object} A dictionary containing the set brightness and color temperature.
    */
    function setLightValues(brightness, color_temp) {
      return {
        brightness: brightness,
        colorTemperature: color_temp
      };
    }

### Step 2: Call the model with function declarations

Once you have defined your function declarations, you can prompt the model to use them. It analyzes the prompt and function declarations and decides whether to respond directly or to call a function. If a function is called, the response object will contain a function call suggestion.  

### Python

    from google.genai import types

    # Configure the client and tools
    client = genai.Client()
    tools = types.Tool(function_declarations=[set_light_values_declaration])
    config = types.GenerateContentConfig(tools=[tools])

    # Define user prompt
    contents = [
        types.Content(
            role="user", parts=[types.Part(text="Turn the lights down to a romantic level")]
        )
    ]

    # Send request with function declarations
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents
        config=config,
    )

    print(response.candidates[0].content.parts[0].function_call)

### JavaScript

    import { GoogleGenAI } from '@google/genai';

    // Generation config with function declaration
    const config = {
      tools: [{
        functionDeclarations: [setLightValuesFunctionDeclaration]
      }]
    };

    // Configure the client
    const ai = new GoogleGenAI({});

    // Define user prompt
    const contents = [
      {
        role: 'user',
        parts: [{ text: 'Turn the lights down to a romantic level' }]
      }
    ];

    // Send request with function declarations
    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: contents,
      config: config
    });

    console.log(response.functionCalls[0]);

The model then returns a`functionCall`object in an OpenAPI compatible schema specifying how to call one or more of the declared functions in order to respond to the user's question.  

### Python

    id=None args={'color_temp': 'warm', 'brightness': 25} name='set_light_values'

### JavaScript

    {
      name: 'set_light_values',
      args: { brightness: 25, color_temp: 'warm' }
    }

### Step 3: Execute set_light_values function code

Extract the function call details from the model's response, parse the arguments , and execute the`set_light_values`function.  

### Python

    # Extract tool call details, it may not be in the first part.
    tool_call = response.candidates[0].content.parts[0].function_call

    if tool_call.name == "set_light_values":
        result = set_light_values(**tool_call.args)
        print(f"Function execution result: {result}")

### JavaScript

    // Extract tool call details
    const tool_call = response.functionCalls[0]

    let result;
    if (tool_call.name === 'set_light_values') {
      result = setLightValues(tool_call.args.brightness, tool_call.args.color_temp);
      console.log(`Function execution result: ${JSON.stringify(result)}`);
    }

### Step 4: Create user friendly response with function result and call the model again

Finally, send the result of the function execution back to the model so it can incorporate this information into its final response to the user.  

### Python

    from google import genai
    from google.genai import types

    # Create a function response part
    function_response_part = types.Part.from_function_response(
        name=tool_call.name,
        response={"result": result},
    )

    # Append function call and result of the function execution to contents
    contents.append(response.candidates[0].content) # Append the content from the model's response.
    contents.append(types.Content(role="user", parts=[function_response_part])) # Append the function response

    client = genai.Client()
    final_response = client.models.generate_content(
        model="gemini-2.5-flash",
        config=config,
        contents=contents,
    )

    print(final_response.text)

### JavaScript

    // Create a function response part
    const function_response_part = {
      name: tool_call.name,
      response: { result }
    }

    // Append function call and result of the function execution to contents
    contents.push(response.candidates[0].content);
    contents.push({ role: 'user', parts: [{ functionResponse: function_response_part }] });

    // Get the final response from the model
    const final_response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: contents,
      config: config
    });

    console.log(final_response.text);

This completes the function calling flow. The model successfully used the`set_light_values`function to perform the request action of the user.

## Function declarations

When you implement function calling in a prompt, you create a`tools`object, which contains one or more`function declarations`. You define functions using JSON, specifically with a[select subset](https://ai.google.dev/api/caching#Schema)of the[OpenAPI schema](https://spec.openapis.org/oas/v3.0.3#schemaw)format. A single function declaration can include the following parameters:

- `name`(string): A unique name for the function (`get_weather_forecast`,`send_email`). Use descriptive names without spaces or special characters (use underscores or camelCase).
- `description`(string): A clear and detailed explanation of the function's purpose and capabilities. This is crucial for the model to understand when to use the function. Be specific and provide examples if helpful ("Finds theaters based on location and optionally movie title which is currently playing in theaters.").
- `parameters`(object): Defines the input parameters the function expects.
  - `type`(string): Specifies the overall data type, such as`object`.
  - `properties`(object): Lists individual parameters, each with:
    - `type`(string): The data type of the parameter, such as`string`,`integer`,`boolean, array`.
    - `description`(string): A description of the parameter's purpose and format. Provide examples and constraints ("The city and state, e.g., 'San Francisco, CA' or a zip code e.g., '95616'.").
    - `enum`(array, optional): If the parameter values are from a fixed set, use "enum" to list the allowed values instead of just describing them in the description. This improves accuracy ("enum": \["daylight", "cool", "warm"\]).
  - `required`(array): An array of strings listing the parameter names that are mandatory for the function to operate.

You can also construct`FunctionDeclarations`from Python functions directly using`types.FunctionDeclaration.from_callable(client=client, callable=your_function)`.

## Function calling with thinking models

Gemini 3 and 2.5 series models use an internal["thinking"](https://ai.google.dev/gemini-api/docs/thinking)process to reason through requests. This significantly improves function calling performance, allowing the model to better determine when to call a function and which parameters to use. Because the Gemini API is stateless, models use[thought signatures](https://ai.google.dev/gemini-api/docs/thought-signatures)to maintain context across multi-turn conversations.

This section covers advanced management of thought signatures and is only necessary if you're manually constructing API requests (e.g., via REST) or manipulating conversation history.

**If you're using the[Google GenAI SDKs](https://ai.google.dev/gemini-api/docs/libraries)(our official libraries), you don't need to manage this process** . The SDKs automatically handle the necessary steps, as shown in the earlier[example](https://ai.google.dev/gemini-api/docs/function-calling#step-4).

### Managing conversation history manually

If you modify the conversation history manually, instead of sending the[complete previous response](https://ai.google.dev/gemini-api/docs/function-calling#step-4)you must correctly handle the`thought_signature`included in the model's turn.

Follow these rules to ensure the model's context is preserved:

- Always send the`thought_signature`back to the model inside its original[`Part`](https://ai.google.dev/api#request-body-structure).
- Don't merge a`Part`containing a signature with one that does not. This breaks the positional context of the thought.
- Don't combine two`Parts`that both contain signatures, as the signature strings cannot be merged.

#### Gemini 3 thought signatures

In Gemini 3, any[`Part`](https://ai.google.dev/api#request-body-structure)of a model response may contain a thought signature. While we generally recommend returning signatures from all`Part`types, passing back thought signatures is mandatory for function calling. Unless you are manipulating conversation history manually, the Google GenAI SDK will handle thought signatures automatically.

If you are manipulating conversation history manually, refer to the[Thoughts Signatures](https://ai.google.dev/gemini-api/docs/thought-signatures)page for complete guidance and details on handling thought signatures for Gemini 3.

### Inspecting thought signatures

While not necessary for implementation, you can inspect the response to see the`thought_signature`for debugging or educational purposes.  

### Python

    import base64
    # After receiving a response from a model with thinking enabled
    # response = client.models.generate_content(...)

    # The signature is attached to the response part containing the function call
    part = response.candidates[0].content.parts[0]
    if part.thought_signature:
      print(base64.b64encode(part.thought_signature).decode("utf-8"))

### JavaScript

    // After receiving a response from a model with thinking enabled
    // const response = await ai.models.generateContent(...)

    // The signature is attached to the response part containing the function call
    const part = response.candidates[0].content.parts[0];
    if (part.thoughtSignature) {
      console.log(part.thoughtSignature);
    }

Learn more about limitations and usage of thought signatures, and about thinking models in general, on the[Thinking](https://ai.google.dev/gemini-api/docs/thinking#signatures)page.

## Parallel function calling

In addition to single turn function calling, you can also call multiple functions at once. Parallel function calling lets you execute multiple functions at once and is used when the functions are not dependent on each other. This is useful in scenarios like gathering data from multiple independent sources, such as retrieving customer details from different databases or checking inventory levels across various warehouses or performing multiple actions such as converting your apartment into a disco.  

### Python

    power_disco_ball = {
        "name": "power_disco_ball",
        "description": "Powers the spinning disco ball.",
        "parameters": {
            "type": "object",
            "properties": {
                "power": {
                    "type": "boolean",
                    "description": "Whether to turn the disco ball on or off.",
                }
            },
            "required": ["power"],
        },
    }

    start_music = {
        "name": "start_music",
        "description": "Play some music matching the specified parameters.",
        "parameters": {
            "type": "object",
            "properties": {
                "energetic": {
                    "type": "boolean",
                    "description": "Whether the music is energetic or not.",
                },
                "loud": {
                    "type": "boolean",
                    "description": "Whether the music is loud or not.",
                },
            },
            "required": ["energetic", "loud"],
        },
    }

    dim_lights = {
        "name": "dim_lights",
        "description": "Dim the lights.",
        "parameters": {
            "type": "object",
            "properties": {
                "brightness": {
                    "type": "number",
                    "description": "The brightness of the lights, 0.0 is off, 1.0 is full.",
                }
            },
            "required": ["brightness"],
        },
    }

### JavaScript

    import { Type } from '@google/genai';

    const powerDiscoBall = {
      name: 'power_disco_ball',
      description: 'Powers the spinning disco ball.',
      parameters: {
        type: Type.OBJECT,
        properties: {
          power: {
            type: Type.BOOLEAN,
            description: 'Whether to turn the disco ball on or off.'
          }
        },
        required: ['power']
      }
    };

    const startMusic = {
      name: 'start_music',
      description: 'Play some music matching the specified parameters.',
      parameters: {
        type: Type.OBJECT,
        properties: {
          energetic: {
            type: Type.BOOLEAN,
            description: 'Whether the music is energetic or not.'
          },
          loud: {
            type: Type.BOOLEAN,
            description: 'Whether the music is loud or not.'
          }
        },
        required: ['energetic', 'loud']
      }
    };

    const dimLights = {
      name: 'dim_lights',
      description: 'Dim the lights.',
      parameters: {
        type: Type.OBJECT,
        properties: {
          brightness: {
            type: Type.NUMBER,
            description: 'The brightness of the lights, 0.0 is off, 1.0 is full.'
          }
        },
        required: ['brightness']
      }
    };

Configure the function calling mode to allow using all of the specified tools. To learn more, you can read about[configuring function calling](https://ai.google.dev/gemini-api/docs/function-calling#function_calling_modes).  

### Python

    from google import genai
    from google.genai import types

    # Configure the client and tools
    client = genai.Client()
    house_tools = [
        types.Tool(function_declarations=[power_disco_ball, start_music, dim_lights])
    ]
    config = types.GenerateContentConfig(
        tools=house_tools,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True
        ),
        # Force the model to call 'any' function, instead of chatting.
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode='ANY')
        ),
    )

    chat = client.chats.create(model="gemini-2.5-flash", config=config)
    response = chat.send_message("Turn this place into a party!")

    # Print out each of the function calls requested from this single call
    print("Example 1: Forced function calling")
    for fn in response.function_calls:
        args = ", ".join(f"{key}={val}" for key, val in fn.args.items())
        print(f"{fn.name}({args})")

### JavaScript

    import { GoogleGenAI } from '@google/genai';

    // Set up function declarations
    const houseFns = [powerDiscoBall, startMusic, dimLights];

    const config = {
        tools: [{
            functionDeclarations: houseFns
        }],
        // Force the model to call 'any' function, instead of chatting.
        toolConfig: {
            functionCallingConfig: {
                mode: 'any'
            }
        }
    };

    // Configure the client
    const ai = new GoogleGenAI({});

    // Create a chat session
    const chat = ai.chats.create({
        model: 'gemini-2.5-flash',
        config: config
    });
    const response = await chat.sendMessage({message: 'Turn this place into a party!'});

    // Print out each of the function calls requested from this single call
    console.log("Example 1: Forced function calling");
    for (const fn of response.functionCalls) {
        const args = Object.entries(fn.args)
            .map(([key, val]) => `${key}=${val}`)
            .join(', ');
        console.log(`${fn.name}(${args})`);
    }

Each of the printed results reflects a single function call that the model has requested. To send the results back, include the responses in the same order as they were requested.

The Python SDK supports[automatic function calling](https://ai.google.dev/gemini-api/docs/function-calling#automatic_function_calling_python_only), which automatically converts Python functions to declarations, handles the function call execution and response cycle for you. Following is an example for the disco use case.
**Note:** Automatic Function Calling is a Python SDK only feature at the moment.  

### Python

    from google import genai
    from google.genai import types

    # Actual function implementations
    def power_disco_ball_impl(power: bool) -> dict:
        """Powers the spinning disco ball.

        Args:
            power: Whether to turn the disco ball on or off.

        Returns:
            A status dictionary indicating the current state.
        """
        return {"status": f"Disco ball powered {'on' if power else 'off'}"}

    def start_music_impl(energetic: bool, loud: bool) -> dict:
        """Play some music matching the specified parameters.

        Args:
            energetic: Whether the music is energetic or not.
            loud: Whether the music is loud or not.

        Returns:
            A dictionary containing the music settings.
        """
        music_type = "energetic" if energetic else "chill"
        volume = "loud" if loud else "quiet"
        return {"music_type": music_type, "volume": volume}

    def dim_lights_impl(brightness: float) -> dict:
        """Dim the lights.

        Args:
            brightness: The brightness of the lights, 0.0 is off, 1.0 is full.

        Returns:
            A dictionary containing the new brightness setting.
        """
        return {"brightness": brightness}

    # Configure the client
    client = genai.Client()
    config = types.GenerateContentConfig(
        tools=[power_disco_ball_impl, start_music_impl, dim_lights_impl]
    )

    # Make the request
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Do everything you need to this place into party!",
        config=config,
    )

    print("\nExample 2: Automatic function calling")
    print(response.text)
    # I've turned on the disco ball, started playing loud and energetic music, and dimmed the lights to 50% brightness. Let's get this party started!

## Compositional function calling

Compositional or sequential function calling allows Gemini to chain multiple function calls together to fulfill a complex request. For example, to answer "Get the temperature in my current location", the Gemini API might first invoke a`get_current_location()`function followed by a`get_weather()`function that takes the location as a parameter.

The following example demonstrates how to implement compositional function calling using the Python SDK and automatic function calling.  

### Python

This example uses the automatic function calling feature of the`google-genai`Python SDK. The SDK automatically converts the Python functions to the required schema, executes the function calls when requested by the model, and sends the results back to the model to complete the task.  

    import os
    from google import genai
    from google.genai import types

    # Example Functions
    def get_weather_forecast(location: str) -> dict:
        """Gets the current weather temperature for a given location."""
        print(f"Tool Call: get_weather_forecast(location={location})")
        # TODO: Make API call
        print("Tool Response: {'temperature': 25, 'unit': 'celsius'}")
        return {"temperature": 25, "unit": "celsius"}  # Dummy response

    def set_thermostat_temperature(temperature: int) -> dict:
        """Sets the thermostat to a desired temperature."""
        print(f"Tool Call: set_thermostat_temperature(temperature={temperature})")
        # TODO: Interact with a thermostat API
        print("Tool Response: {'status': 'success'}")
        return {"status": "success"}

    # Configure the client and model
    client = genai.Client()
    config = types.GenerateContentConfig(
        tools=[get_weather_forecast, set_thermostat_temperature]
    )

    # Make the request
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="If it's warmer than 20°C in London, set the thermostat to 20°C, otherwise set it to 18°C.",
        config=config,
    )

    # Print the final, user-facing response
    print(response.text)

**Expected Output**

When you run the code, you will see the SDK orchestrating the function calls. The model first calls`get_weather_forecast`, receives the temperature, and then calls`set_thermostat_temperature`with the correct value based on the logic in the prompt.  

    Tool Call: get_weather_forecast(location=London)
    Tool Response: {'temperature': 25, 'unit': 'celsius'}
    Tool Call: set_thermostat_temperature(temperature=20)
    Tool Response: {'status': 'success'}
    OK. I've set the thermostat to 20°C.

### JavaScript

This example shows how to use JavaScript/TypeScript SDK to do comopositional function calling using a manual execution loop.  

    import { GoogleGenAI, Type } from "@google/genai";

    // Configure the client
    const ai = new GoogleGenAI({});

    // Example Functions
    function get_weather_forecast({ location }) {
      console.log(`Tool Call: get_weather_forecast(location=${location})`);
      // TODO: Make API call
      console.log("Tool Response: {'temperature': 25, 'unit': 'celsius'}");
      return { temperature: 25, unit: "celsius" };
    }

    function set_thermostat_temperature({ temperature }) {
      console.log(
        `Tool Call: set_thermostat_temperature(temperature=${temperature})`,
      );
      // TODO: Make API call
      console.log("Tool Response: {'status': 'success'}");
      return { status: "success" };
    }

    const toolFunctions = {
      get_weather_forecast,
      set_thermostat_temperature,
    };

    const tools = [
      {
        functionDeclarations: [
          {
            name: "get_weather_forecast",
            description:
              "Gets the current weather temperature for a given location.",
            parameters: {
              type: Type.OBJECT,
              properties: {
                location: {
                  type: Type.STRING,
                },
              },
              required: ["location"],
            },
          },
          {
            name: "set_thermostat_temperature",
            description: "Sets the thermostat to a desired temperature.",
            parameters: {
              type: Type.OBJECT,
              properties: {
                temperature: {
                  type: Type.NUMBER,
                },
              },
              required: ["temperature"],
            },
          },
        ],
      },
    ];

    // Prompt for the model
    let contents = [
      {
        role: "user",
        parts: [
          {
            text: "If it's warmer than 20°C in London, set the thermostat to 20°C, otherwise set it to 18°C.",
          },
        ],
      },
    ];

    // Loop until the model has no more function calls to make
    while (true) {
      const result = await ai.models.generateContent({
        model: "gemini-2.5-flash",
        contents,
        config: { tools },
      });

      if (result.functionCalls && result.functionCalls.length > 0) {
        const functionCall = result.functionCalls[0];

        const { name, args } = functionCall;

        if (!toolFunctions[name]) {
          throw new Error(`Unknown function call: ${name}`);
        }

        // Call the function and get the response.
        const toolResponse = toolFunctions[name](args);

        const functionResponsePart = {
          name: functionCall.name,
          response: {
            result: toolResponse,
          },
        };

        // Send the function response back to the model.
        contents.push({
          role: "model",
          parts: [
            {
              functionCall: functionCall,
            },
          ],
        });
        contents.push({
          role: "user",
          parts: [
            {
              functionResponse: functionResponsePart,
            },
          ],
        });
      } else {
        // No more function calls, break the loop.
        console.log(result.text);
        break;
      }
    }

**Expected Output**

When you run the code, you will see the SDK orchestrating the function calls. The model first calls`get_weather_forecast`, receives the temperature, and then calls`set_thermostat_temperature`with the correct value based on the logic in the prompt.  

    Tool Call: get_weather_forecast(location=London)
    Tool Response: {'temperature': 25, 'unit': 'celsius'}
    Tool Call: set_thermostat_temperature(temperature=20)
    Tool Response: {'status': 'success'}
    OK. It's 25°C in London, so I've set the thermostat to 20°C.

Compositional function calling is a native[Live API](https://ai.google.dev/gemini-api/docs/live)feature. This means Live API can handle the function calling similar to the Python SDK.  

### Python

    # Light control schemas
    turn_on_the_lights_schema = {'name': 'turn_on_the_lights'}
    turn_off_the_lights_schema = {'name': 'turn_off_the_lights'}

    prompt = """
      Hey, can you write run some python code to turn on the lights, wait 10s and then turn off the lights?
      """

    tools = [
        {'code_execution': {}},
        {'function_declarations': [turn_on_the_lights_schema, turn_off_the_lights_schema]}
    ]

    await run(prompt, tools=tools, modality="AUDIO")

### JavaScript

    // Light control schemas
    const turnOnTheLightsSchema = { name: 'turn_on_the_lights' };
    const turnOffTheLightsSchema = { name: 'turn_off_the_lights' };

    const prompt = `
      Hey, can you write run some python code to turn on the lights, wait 10s and then turn off the lights?
    `;

    const tools = [
      { codeExecution: {} },
      { functionDeclarations: [turnOnTheLightsSchema, turnOffTheLightsSchema] }
    ];

    await run(prompt, tools=tools, modality="AUDIO")

## Function calling modes

The Gemini API lets you control how the model uses the provided tools (function declarations). Specifically, you can set the mode within the.`function_calling_config`.

- `AUTO (Default)`: The model decides whether to generate a natural language response or suggest a function call based on the prompt and context. This is the most flexible mode and recommended for most scenarios.
- `ANY`: The model is constrained to always predict a function call and guarantees function schema adherence. If`allowed_function_names`is not specified, the model can choose from any of the provided function declarations. If`allowed_function_names`is provided as a list, the model can only choose from the functions in that list. Use this mode when you require a function call response to every prompt (if applicable).
- `NONE`: The model is*prohibited*from making function calls. This is equivalent to sending a request without any function declarations. Use this to temporarily disable function calling without removing your tool definitions.
- `VALIDATED`(Preview): The model is constrained to predict either function calls or natural language, and ensures function schema adherence. If`allowed_function_names`is not provided, the model picks from all of the available function declarations. If`allowed_function_names`is provided, the model picks from the set of allowed functions.

### Python

    from google.genai import types

    # Configure function calling mode
    tool_config = types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(
            mode="ANY", allowed_function_names=["get_current_temperature"]
        )
    )

    # Create the generation config
    config = types.GenerateContentConfig(
        tools=[tools],  # not defined here.
        tool_config=tool_config,
    )

### JavaScript

    import { FunctionCallingConfigMode } from '@google/genai';

    // Configure function calling mode
    const toolConfig = {
      functionCallingConfig: {
        mode: FunctionCallingConfigMode.ANY,
        allowedFunctionNames: ['get_current_temperature']
      }
    };

    // Create the generation config
    const config = {
      tools: tools, // not defined here.
      toolConfig: toolConfig,
    };

## Automatic function calling (Python only)

When using the Python SDK, you can provide Python functions directly as tools. The SDK converts these functions into declarations, manages the function call execution, and handles the response cycle for you. Define your function with type hints and a docstring. For optimal results, it is recommended to use[Google-style docstrings.](https://google.github.io/styleguide/pyguide.html#383-functions-and-methods)The SDK will then automatically:

1. Detect function call responses from the model.
2. Call the corresponding Python function in your code.
3. Send the function's response back to the model.
4. Return the model's final text response.

The SDK currently does not parse argument descriptions into the property description slots of the generated function declaration. Instead, it sends the entire docstring as the top-level function description.  

### Python

    from google import genai
    from google.genai import types

    # Define the function with type hints and docstring
    def get_current_temperature(location: str) -> dict:
        """Gets the current temperature for a given location.

        Args:
            location: The city and state, e.g. San Francisco, CA

        Returns:
            A dictionary containing the temperature and unit.
        """
        # ... (implementation) ...
        return {"temperature": 25, "unit": "Celsius"}

    # Configure the client
    client = genai.Client()
    config = types.GenerateContentConfig(
        tools=[get_current_temperature]
    )  # Pass the function itself

    # Make the request
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="What's the temperature in Boston?",
        config=config,
    )

    print(response.text)  # The SDK handles the function call and returns the final text

You can disable automatic function calling with:  

### Python

    config = types.GenerateContentConfig(
        tools=[get_current_temperature],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
    )

### Automatic function schema declaration

The API is able to describe any of the following types.`Pydantic`types are allowed, as long as the fields defined on them are also composed of allowed types. Dict types (like`dict[str: int]`) are not well supported here, don't use them.  

### Python

    AllowedType = (
      int | float | bool | str | list['AllowedType'] | pydantic.BaseModel)

To see what the inferred schema looks like, you can convert it using[`from_callable`](https://googleapis.github.io/python-genai/genai.html#genai.types.FunctionDeclaration.from_callable):  

### Python

    from google import genai
    from google.genai import types

    def multiply(a: float, b: float):
        """Returns a * b."""
        return a * b

    client = genai.Client()
    fn_decl = types.FunctionDeclaration.from_callable(callable=multiply, client=client)

    # to_json_dict() provides a clean JSON representation.
    print(fn_decl.to_json_dict())

## Multi-tool use: Combine native tools with function calling

You can enable multiple tools combining native tools with function calling at the same time. Here's an example that enables two tools,[Grounding with Google Search](https://ai.google.dev/gemini-api/docs/grounding)and[code execution](https://ai.google.dev/gemini-api/docs/code-execution), in a request using the[Live API](https://ai.google.dev/gemini-api/docs/live).
**Note:** Multi-tool use is a-[Live API](https://ai.google.dev/gemini-api/docs/live)only feature at the moment. The`run()`function declaration, which handles the asynchronous websocket setup, is omitted for brevity.  

### Python

    # Multiple tasks example - combining lights, code execution, and search
    prompt = """
      Hey, I need you to do three things for me.

        1.  Turn on the lights.
        2.  Then compute the largest prime palindrome under 100000.
        3.  Then use Google Search to look up information about the largest earthquake in California the week of Dec 5 2024.

      Thanks!
      """

    tools = [
        {'google_search': {}},
        {'code_execution': {}},
        {'function_declarations': [turn_on_the_lights_schema, turn_off_the_lights_schema]} # not defined here.
    ]

    # Execute the prompt with specified tools in audio modality
    await run(prompt, tools=tools, modality="AUDIO")

### JavaScript

    // Multiple tasks example - combining lights, code execution, and search
    const prompt = `
      Hey, I need you to do three things for me.

        1.  Turn on the lights.
        2.  Then compute the largest prime palindrome under 100000.
        3.  Then use Google Search to look up information about the largest earthquake in California the week of Dec 5 2024.

      Thanks!
    `;

    const tools = [
      { googleSearch: {} },
      { codeExecution: {} },
      { functionDeclarations: [turnOnTheLightsSchema, turnOffTheLightsSchema] } // not defined here.
    ];

    // Execute the prompt with specified tools in audio modality
    await run(prompt, {tools: tools, modality: "AUDIO"});

Python developers can try this out in the[Live API Tool Use notebook](https://colab.research.google.com/github/google-gemini/cookbook/blob/main/quickstarts/Get_started_LiveAPI_tools.ipynb).

## Multimodal function responses

| **Note:** This feature is available for[Gemini 3](https://ai.google.dev/gemini-api/docs/gemini-3)series models.

For Gemini 3 series models, you can include multimodal content in the function response parts that you send to the model. The model can process this multimodal content in its next turn to produce a more informed response. The following MIME types are supported for multimodal content in function responses:

- **Images** :`image/png`,`image/jpeg`,`image/webp`
- **Documents** :`application/pdf`,`text/plain`

To include multimodal data in a function response, include it as one or more parts nested within the`functionResponse`part. Each multimodal part must contain`inlineData`. If you reference a multimodal part from within the structured`response`field, it must contain a unique`displayName`.

You can also reference a multimodal part from within the structured`response`field of the`functionResponse`part by using the JSON reference format`{"$ref": "<displayName>"}`. The model substitutes the reference with the multimodal content when processing the response. Each`displayName`can only be referenced once in the structured`response`field.

The following example shows a message containing a`functionResponse`for a function named`get_image`and a nested part containing image data with`displayName: "wakeupcat.jpg"`. The`functionResponse`'s`response`field references this image part:  

### Python

    from google import genai
    from google.genai import types

    client = genai.Client()

    # This is a manual, two turn multimodal function calling workflow:

    # 1. Define the function tool
    get_image_declaration = types.FunctionDeclaration(
      name="get_image",
      description="Retrieves the image file reference for a specific order item.",
      parameters={
          "type": "object",
          "properties": {
              "item_name": {
                  "type": "string",
                  "description": "The name or description of the item ordered (e.g., 'green shirt')."
              }
          },
          "required": ["item_name"],
      },
    )
    tool_config = types.Tool(function_declarations=[get_image_declaration])

    # 2. Send a message that triggers the tool
    prompt = "Show me the green shirt I ordered last month."
    response_1 = client.models.generate_content(
      model="gemini-3-flash-preview",
      contents=[prompt],
      config=types.GenerateContentConfig(
          tools=[tool_config],
      )
    )

    # 3. Handle the function call
    function_call = response_1.function_calls[0]
    requested_item = function_call.args["item_name"]
    print(f"Model wants to call: {function_call.name}")

    # Execute your tool (e.g., call an API)
    # (This is a mock response for the example)
    print(f"Calling external tool for: {requested_item}")

    function_response_data = {
      "image_ref": {"$ref": "dress.jpg"},
    }

    function_response_multimodal_data = types.FunctionResponsePart(
      file_data=types.FunctionResponseFileData(
        mime_type="image/png",
        display_name="dress.jpg",
        file_uri="gs://cloud-samples-data/generative-ai/image/dress.jpg",
      )
    )

    # 4. Send the tool's result back
    # Append this turn's messages to history for a final response.
    history = [
      types.Content(role="user", parts=[types.Part(text=prompt)]),
      response_1.candidates[0].content,
      types.Content(
        role="tool",
        parts=[
            types.Part.from_function_response(
              name=function_call.name,
              response=function_response_data,
              parts=[function_response_multimodal_data]
            )
        ],
      )
    ]

    response_2 = client.models.generate_content(
      model="gemini-3-flash-preview",
      contents=history,
      config=types.GenerateContentConfig(
          tools=[tool_config],
          thinking_config=types.ThinkingConfig(include_thoughts=True)
      ),
    )

    print(f"\nFinal model response: {response_2.text}")

### JavaScript

    import { GoogleGenAI, Type } from '@google/genai';

    const client = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

    // This is a manual, two turn multimodal function calling workflow:
    // 1. Define the function tool
    const getImageDeclaration = {
      name: 'get_image',
      description: 'Retrieves the image file reference for a specific order item.',
      parameters: {
        type: Type.OBJECT,
        properties: {
          item_name: {
            type: Type.STRING,
            description: "The name or description of the item ordered (e.g., 'green shirt').",
          },
        },
        required: ['item_name'],
      },
    };

    const toolConfig = {
      functionDeclarations: [getImageDeclaration],
    };

    // 2. Send a message that triggers the tool
    const prompt = 'Show me the green shirt I ordered last month.';
    const response1 = await client.models.generateContent({
      model: 'gemini-3-flash-preview',
      contents: prompt,
      config: {
        tools: [toolConfig],
      },
    });

    // 3. Handle the function call
    const functionCall = response1.functionCalls[0];
    const requestedItem = functionCall.args.item_name;
    console.log(`Model wants to call: ${functionCall.name}`);

    // Execute your tool (e.g., call an API)
    // (This is a mock response for the example)
    console.log(`Calling external tool for: ${requestedItem}`);

    const functionResponseData = {
      image_ref: { $ref: 'dress.jpg' },
    };

    const functionResponseMultimodalData = {
      fileData: {
        mimeType: 'image/png',
        displayName: 'dress.jpg',
        fileUri: 'gs://cloud-samples-data/generative-ai/image/dress.jpg',
      },
    };

    // 4. Send the tool's result back
    // Append this turn's messages to history for a final response.
    const history = [
      { role: 'user', parts: [{ text: prompt }] },
      response1.candidates[0].content,
      {
        role: 'tool',
        parts: [
          {
            functionResponse: {
              name: functionCall.name,
              response: functionResponseData,
              parts: [functionResponseMultimodalData],
            },
          },
        ],
      },
    ];

    const response2 = await client.models.generateContent({
      model: 'gemini-3-flash-preview',
      contents: history,
      config: {
        tools: [toolConfig],
        thinkingConfig: { includeThoughts: true },
      },
    });

    console.log(`\nFinal model response: ${response2.text}`);

### REST

    "contents": [
      ...,
      {
        "role": "user",
        "parts": [
          {
            "functionResponse": {
              "name": "get_image",
              "response": {
                "image_ref": {
                  "$ref": "wakeupcat.jpg"
                }
              },
              "parts": [
                {
                  "fileData": {
                    "displayName": "wakeupcat.jpg",
                    "mimeType": "image/jpeg",
                    "fileUri": "gs://cloud-samples-data/vision/label/wakeupcat.jpg"
                  }
                }
              ]
            }
          }
        ]
      }
    ]

## Model context protocol (MCP)

[Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction)is an open standard for connecting AI applications with external tools and data. MCP provides a common protocol for models to access context, such as functions (tools), data sources (resources), or predefined prompts.

The Gemini SDKs have built-in support for the MCP, reducing boilerplate code and offering[automatic tool calling](https://ai.google.dev/gemini-api/docs/function-calling#automatic_function_calling_python_only)for MCP tools. When the model generates an MCP tool call, the Python and JavaScript client SDK can automatically execute the MCP tool and send the response back to the model in a subsequent request, continuing this loop until no more tool calls are made by the model.

Here, you can find an example of how to use a local MCP server with Gemini and`mcp`SDK.  

### Python

Make sure the latest version of the[`mcp`SDK](https://modelcontextprotocol.io/introduction)is installed on your platform of choice.  

    pip install mcp

**Note:** Python supports automatic tool calling by passing in the`ClientSession`into the`tools`parameters. If you want to disable it, you can provide`automatic_function_calling`with disabled`True`.  

    import os
    import asyncio
    from datetime import datetime
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from google import genai

    client = genai.Client()

    # Create server parameters for stdio connection
    server_params = StdioServerParameters(
        command="npx",  # Executable
        args=["-y", "@philschmid/weather-mcp"],  # MCP Server
        env=None,  # Optional environment variables
    )

    async def run():
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Prompt to get the weather for the current day in London.
                prompt = f"What is the weather in London in {datetime.now().strftime('%Y-%m-%d')}?"

                # Initialize the connection between client and server
                await session.initialize()

                # Send request to the model with MCP function declarations
                response = await client.aio.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        temperature=0,
                        tools=[session],  # uses the session, will automatically call the tool
                        # Uncomment if you **don't** want the SDK to automatically call the tool
                        # automatic_function_calling=genai.types.AutomaticFunctionCallingConfig(
                        #     disable=True
                        # ),
                    ),
                )
                print(response.text)

    # Start the asyncio event loop and run the main function
    asyncio.run(run())

### JavaScript

Make sure the latest version of the`mcp`SDK is installed on your platform of choice.  

    npm install @modelcontextprotocol/sdk

**Note:** JavaScript supports automatic tool calling by wrapping the`client`with`mcpToTool`. If you want to disable it, you can provide`automaticFunctionCalling`with disabled`true`.  

    import { GoogleGenAI, FunctionCallingConfigMode , mcpToTool} from '@google/genai';
    import { Client } from "@modelcontextprotocol/sdk/client/index.js";
    import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

    // Create server parameters for stdio connection
    const serverParams = new StdioClientTransport({
      command: "npx", // Executable
      args: ["-y", "@philschmid/weather-mcp"] // MCP Server
    });

    const client = new Client(
      {
        name: "example-client",
        version: "1.0.0"
      }
    );

    // Configure the client
    const ai = new GoogleGenAI({});

    // Initialize the connection between client and server
    await client.connect(serverParams);

    // Send request to the model with MCP tools
    const response = await ai.models.generateContent({
      model: "gemini-2.5-flash",
      contents: `What is the weather in London in ${new Date().toLocaleDateString()}?`,
      config: {
        tools: [mcpToTool(client)],  // uses the session, will automatically call the tool
        // Uncomment if you **don't** want the sdk to automatically call the tool
        // automaticFunctionCalling: {
        //   disable: true,
        // },
      },
    });
    console.log(response.text)

    // Close the connection
    await client.close();

### Limitations with built-in MCP support

Built-in MCP support is a[experimental](https://ai.google.dev/gemini-api/docs/models#preview)feature in our SDKs and has the following limitations:

- Only tools are supported, not resources nor prompts
- It is available for the Python and JavaScript/TypeScript SDK.
- Breaking changes might occur in future releases.

Manual integration of MCP servers is always an option if these limit what you're building.

## Supported models

This section lists models and their function calling capabilities. Experimental models are not included. You can find a comprehensive capabilities overview on the[model overview](https://ai.google.dev/gemini-api/docs/models)page.

|         Model         | Function Calling | Parallel Function Calling | Compositional Function Calling |
|-----------------------|------------------|---------------------------|--------------------------------|
| Gemini 3 Pro          | ✔️               | ✔️                        | ✔️                             |
| Gemini 3 Flash        | ✔️               | ✔️                        | ✔️                             |
| Gemini 2.5 Pro        | ✔️               | ✔️                        | ✔️                             |
| Gemini 2.5 Flash      | ✔️               | ✔️                        | ✔️                             |
| Gemini 2.5 Flash-Lite | ✔️               | ✔️                        | ✔️                             |
| Gemini 2.0 Flash      | ✔️               | ✔️                        | ✔️                             |
| Gemini 2.0 Flash-Lite | X                | X                         | X                              |

## Best practices

- **Function and Parameter Descriptions:**Be extremely clear and specific in your descriptions. The model relies on these to choose the correct function and provide appropriate arguments.
- **Naming:**Use descriptive function names (without spaces, periods, or dashes).
- **Strong Typing:**Use specific types (integer, string, enum) for parameters to reduce errors. If a parameter has a limited set of valid values, use an enum.
- **Tool Selection:**While the model can use an arbitrary number of tools, providing too many can increase the risk of selecting an incorrect or suboptimal tool. For best results, aim to provide only the relevant tools for the context or task, ideally keeping the active set to a maximum of 10-20. Consider dynamic tool selection based on conversation context if you have a large total number of tools.
- **Prompt Engineering:**
  - Provide context: Tell the model its role (e.g., "You are a helpful weather assistant.").
  - Give instructions: Specify how and when to use functions (e.g., "Don't guess dates; always use a future date for forecasts.").
  - Encourage clarification: Instruct the model to ask clarifying questions if needed.
  - See[Agentic workflows](https://ai.google.dev/gemini-api/docs/prompting-strategies#agentic-workflows)for further strategies on designing these prompts. Here is an example of a tested[system instruction](https://ai.google.dev/gemini-api/docs/prompting-strategies#agentic-si-template).
- **Temperature:**Use a low temperature (e.g., 0) for more deterministic and reliable function calls.

  | When using Gemini 3 models, we strongly recommend keeping the`temperature`at its default value of 1.0. Changing the temperature (setting it below 1.0) may lead to unexpected behavior, such as looping or degraded performance, particularly in complex mathematical or reasoning tasks.
- **Validation:**If a function call has significant consequences (e.g., placing an order), validate the call with the user before executing it.

- **Check Finish Reason:** Always check the[`finishReason`](https://ai.google.dev/api/generate-content#FinishReason)in the model's response to handle cases where the model failed to generate a valid function call.

- **Error Handling**: Implement robust error handling in your functions to gracefully handle unexpected inputs or API failures. Return informative error messages that the model can use to generate helpful responses to the user.

- **Security:**Be mindful of security when calling external APIs. Use appropriate authentication and authorization mechanisms. Avoid exposing sensitive data in function calls.

- **Token Limits:**Function descriptions and parameters count towards your input token limit. If you're hitting token limits, consider limiting the number of functions or the length of the descriptions, break down complex tasks into smaller, more focused function sets.

## Notes and limitations

- Only a[subset of the OpenAPI schema](https://ai.google.dev/api/caching#FunctionDeclaration)is supported.
- Supported parameter types in Python are limited.
- Automatic function calling is a Python SDK feature only.<br />

The Gemini API provides a code execution tool that enables the model to generate and run Python code. The model can then learn iteratively from the code execution results until it arrives at a final output. You can use code execution to build applications that benefit from code-based reasoning. For example, you can use code execution to solve equations or process text. You can also use the[libraries](https://ai.google.dev/gemini-api/docs/code-execution#supported-libraries)included in the code execution environment to perform more specialized tasks.

Gemini is only able to execute code in Python. You can still ask Gemini to generate code in another language, but the model can't use the code execution tool to run it.

## Enable code execution

To enable code execution, configure the code execution tool on the model. This allows the model to generate and run code.  

### Python

    from google import genai
    from google.genai import types

    client = genai.Client()

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="What is the sum of the first 50 prime numbers? "
        "Generate and run code for the calculation, and make sure you get all 50.",
        config=types.GenerateContentConfig(
            tools=[types.Tool(code_execution=types.ToolCodeExecution)]
        ),
    )

    for part in response.candidates[0].content.parts:
        if part.text is not None:
            print(part.text)
        if part.executable_code is not None:
            print(part.executable_code.code)
        if part.code_execution_result is not None:
            print(part.code_execution_result.output)

### JavaScript

    import { GoogleGenAI } from "@google/genai";

    const ai = new GoogleGenAI({});

    let response = await ai.models.generateContent({
      model: "gemini-2.5-flash",
      contents: [
        "What is the sum of the first 50 prime numbers? " +
          "Generate and run code for the calculation, and make sure you get all 50.",
      ],
      config: {
        tools: [{ codeExecution: {} }],
      },
    });

    const parts = response?.candidates?.[0]?.content?.parts || [];
    parts.forEach((part) => {
      if (part.text) {
        console.log(part.text);
      }

      if (part.executableCode && part.executableCode.code) {
        console.log(part.executableCode.code);
      }

      if (part.codeExecutionResult && part.codeExecutionResult.output) {
        console.log(part.codeExecutionResult.output);
      }
    });

### Go

    package main

    import (
        "context"
        "fmt"
        "os"
        "google.golang.org/genai"
    )

    func main() {

        ctx := context.Background()
        client, err := genai.NewClient(ctx, nil)
        if err != nil {
            log.Fatal(err)
        }

        config := &genai.GenerateContentConfig{
            Tools: []*genai.Tool{
                {CodeExecution: &genai.ToolCodeExecution{}},
            },
        }

        result, _ := client.Models.GenerateContent(
            ctx,
            "gemini-2.5-flash",
            genai.Text("What is the sum of the first 50 prime numbers? " +
                      "Generate and run code for the calculation, and make sure you get all 50."),
            config,
        )

        fmt.Println(result.Text())
        fmt.Println(result.ExecutableCode())
        fmt.Println(result.CodeExecutionResult())
    }

### REST

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" \
    -H "x-goog-api-key: $GEMINI_API_KEY" \
    -H 'Content-Type: application/json' \
    -d ' {"tools": [{"code_execution": {}}],
        "contents": {
          "parts":
            {
                "text": "What is the sum of the first 50 prime numbers? Generate and run code for the calculation, and make sure you get all 50."
            }
        },
    }'

| **Note:** This REST example doesn't parse the JSON response as shown in the example output.

The output might look something like the following, which has been formatted for readability:  

    Okay, I need to calculate the sum of the first 50 prime numbers. Here's how I'll
    approach this:

    1.  **Generate Prime Numbers:** I'll use an iterative method to find prime
        numbers. I'll start with 2 and check if each subsequent number is divisible
        by any number between 2 and its square root. If not, it's a prime.
    2.  **Store Primes:** I'll store the prime numbers in a list until I have 50 of
        them.
    3.  **Calculate the Sum:**  Finally, I'll sum the prime numbers in the list.

    Here's the Python code to do this:

    def is_prime(n):
      """Efficiently checks if a number is prime."""
      if n <= 1:
        return False
      if n <= 3:
        return True
      if n % 2 == 0 or n % 3 == 0:
        return False
      i = 5
      while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
          return False
        i += 6
      return True

    primes = []
    num = 2
    while len(primes) < 50:
      if is_prime(num):
        primes.append(num)
      num += 1

    sum_of_primes = sum(primes)
    print(f'{primes=}')
    print(f'{sum_of_primes=}')

    primes=[2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67,
    71, 73, 79, 83, 89, 97, 101, 103, 107, 109, 113, 127, 131, 137, 139, 149, 151,
    157, 163, 167, 173, 179, 181, 191, 193, 197, 199, 211, 223, 227, 229]
    sum_of_primes=5117

    The sum of the first 50 prime numbers is 5117.

This output combines several content parts that the model returns when using code execution:

- `text`: Inline text generated by the model
- `executableCode`: Code generated by the model that is meant to be executed
- `codeExecutionResult`: Result of the executable code

The naming conventions for these parts vary by programming language.

## Code Execution with images (Gemini 3)

The Gemini 3 Flash model can now write and execute Python code to actively manipulate and inspect images. This capability is called*Visual Thinking*.

**Use cases**

- **Zoom and inspect**: The model implicitly detects when details are too small (e.g., reading a distant gauge) and writes code to crop and re-examine the area at higher resolution.
- **Visual math**: The model can run multi-step calculations using code (e.g., summing line items on a receipt).
- **Image annotation**: The model can annotate images to answer questions, such as drawing arrows to show relationships.

| **Note:** While the model automatically handles zooming for small details, you should prompt it explicitly to use code for other tasks, such as "Write code to count the number of gears" or "Rotate this image to make it upright".

### Enabling visual thinking

Visual Thinking is officially supported in Gemini 3 Flash. You can activate this behavior by enabling both Code Execution as a tool and Thinking.  

### Python

    from google import genai
    from google.genai import types
    import requests
    from PIL import Image
    import io

    image_path = "https://goo.gle/instrument-img"
    image_bytes = requests.get(image_path).content
    image = types.Part.from_bytes(
      data=image_bytes, mime_type="image/jpeg"
    )

    # Ensure you have your API key set
    client = genai.Client(api_key="GEMINI_API_KEY")

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[image, "Zoom into the expression pedals and tell me how many pedals are there?"],
        config=types.GenerateContentConfig(
            tools=[types.Tool(code_execution=types.ToolCodeExecution)]
        ),
    )

    for part in response.candidates[0].content.parts:
        if part.text is not None:
            print(part.text)
        if part.executable_code is not None:
            print(part.executable_code.code)
        if part.code_execution_result is not None:
            print(part.code_execution_result.output)
        if part.as_image() is not None:
            # display() is a standard function in Jupyter/Colab notebooks
            display(Image.open(io.BytesIO(part.as_image().image_bytes)))

### JavaScript

    async function main() {
      const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

      // 1. Prepare Image Data
      const imageUrl = "https://goo.gle/instrument-img";
      const response = await fetch(imageUrl);
      const imageArrayBuffer = await response.arrayBuffer();
      const base64ImageData = Buffer.from(imageArrayBuffer).toString('base64');

      // 2. Call the API with Code Execution enabled
      const result = await ai.models.generateContent({
        model: "gemini-3-flash-preview",
        contents: [
          {
            inlineData: {
              mimeType: 'image/jpeg',
              data: base64ImageData,
            },
          },
          { text: "Zoom into the expression pedals and tell me how many pedals are there?" }
        ],
        config: {
          tools: [{ codeExecution: {} }],
        },
      });

      // 3. Process the response (Text, Code, and Execution Results)
      const candidates = result.response.candidates;
      if (candidates && candidates[0].content.parts) {
        for (const part of candidates[0].content.parts) {
          if (part.text) {
            console.log("Text:", part.text);
          }
          if (part.executableCode) {
            console.log(`\nGenerated Code (${part.executableCode.language}):\n`, part.executableCode.code);
          }
          if (part.codeExecutionResult) {
            console.log(`\nExecution Output (${part.codeExecutionResult.outcome}):\n`, part.codeExecutionResult.output);
          }
        }
      }
    }

    main();

### Go

    package main

    import (
        "context"
        "fmt"
        "io"
        "log"
        "net/http"
        "os"

        "google.golang.org/genai"
    )

    func main() {
        ctx := context.Background()
        // Initialize Client (Reads GEMINI_API_KEY from env)
        client, err := genai.NewClient(ctx, nil)
        if err != nil {
            log.Fatal(err)
        }

        // 1. Download the image
        imageResp, err := http.Get("https://goo.gle/instrument-img")
        if err != nil {
            log.Fatal(err)
        }
        defer imageResp.Body.Close()

        imageBytes, err := io.ReadAll(imageResp.Body)
        if err != nil {
            log.Fatal(err)
        }

        // 2. Configure Code Execution Tool
        config := &genai.GenerateContentConfig{
            Tools: []*genai.Tool{
                {CodeExecution: &genai.ToolCodeExecution{}},
            },
        }

        // 3. Generate Content
        result, err := client.Models.GenerateContent(
            ctx,
            "gemini-3-flash-preview",
            []*genai.Content{
                {
                    Parts: []*genai.Part{
                        {InlineData: &genai.Blob{MIMEType: "image/jpeg", Data: imageBytes}},
                        {Text: "Zoom into the expression pedals and tell me how many pedals are there?"},
                    },
                    Role: "user",
                },
            },
            config,
        )
        if err != nil {
            log.Fatal(err)
        }

        // 4. Parse Response (Text, Code, Output)
        for _, cand := range result.Candidates {
            for _, part := range cand.Content.Parts {
                if part.Text != "" {
                    fmt.Println("Text:", part.Text)
                }
                if part.ExecutableCode != nil {
                    fmt.Printf("\nGenerated Code (%s):\n%s\n", 
                        part.ExecutableCode.Language, 
                        part.ExecutableCode.Code)
                }
                if part.CodeExecutionResult != nil {
                    fmt.Printf("\nExecution Output (%s):\n%s\n", 
                        part.CodeExecutionResult.Outcome, 
                        part.CodeExecutionResult.Output)
                }
            }
        }
    }

### REST

    IMG_URL="https://goo.gle/instrument-img"
    MODEL="gemini-3-flash-preview"

    MIME_TYPE=$(curl -sIL "$IMG_URL" | grep -i '^content-type:' | awk -F ': ' '{print $2}' | sed 's/\r$//' | head -n 1)
    if [[ -z "$MIME_TYPE" || ! "$MIME_TYPE" == image/* ]]; then
      MIME_TYPE="image/jpeg"
    fi

    if [[ "$(uname)" == "Darwin" ]]; then
      IMAGE_B64=$(curl -sL "$IMG_URL" | base64 -b 0)
    elif [[ "$(base64 --version 2>&1)" = *"FreeBSD"* ]]; then
      IMAGE_B64=$(curl -sL "$IMG_URL" | base64)
    else
      IMAGE_B64=$(curl -sL "$IMG_URL" | base64 -w0)
    fi

    curl "https://generativelanguage.googleapis.com/v1beta/models/$MODEL:generateContent?key=$GEMINI_API_KEY" \
        -H 'Content-Type: application/json' \
        -X POST \
        -d '{
          "contents": [{
            "parts":[
                {
                  "inline_data": {
                    "mime_type":"'"$MIME_TYPE"'",
                    "data": "'"$IMAGE_B64"'"
                  }
                },
                {"text": "Zoom into the expression pedals and tell me how many pedals are there?"}
            ]
          }],
          "tools": [
            {
              "code_execution": {}
            }
          ]
        }'

## Use code execution in chat

You can also use code execution as part of a chat.  

### Python

    from google import genai
    from google.genai import types

    client = genai.Client()

    chat = client.chats.create(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            tools=[types.Tool(code_execution=types.ToolCodeExecution)]
        ),
    )

    response = chat.send_message("I have a math question for you.")
    print(response.text)

    response = chat.send_message(
        "What is the sum of the first 50 prime numbers? "
        "Generate and run code for the calculation, and make sure you get all 50."
    )

    for part in response.candidates[0].content.parts:
        if part.text is not None:
            print(part.text)
        if part.executable_code is not None:
            print(part.executable_code.code)
        if part.code_execution_result is not None:
            print(part.code_execution_result.output)

### JavaScript

    import {GoogleGenAI} from "@google/genai";

    const ai = new GoogleGenAI({});

    const chat = ai.chats.create({
      model: "gemini-2.5-flash",
      history: [
        {
          role: "user",
          parts: [{ text: "I have a math question for you:" }],
        },
        {
          role: "model",
          parts: [{ text: "Great! I'm ready for your math question. Please ask away." }],
        },
      ],
      config: {
        tools: [{codeExecution:{}}],
      }
    });

    const response = await chat.sendMessage({
      message: "What is the sum of the first 50 prime numbers? " +
                "Generate and run code for the calculation, and make sure you get all 50."
    });
    console.log("Chat response:", response.text);

### Go

    package main

    import (
        "context"
        "fmt"
        "os"
        "google.golang.org/genai"
    )

    func main() {

        ctx := context.Background()
        client, err := genai.NewClient(ctx, nil)
        if err != nil {
            log.Fatal(err)
        }

        config := &genai.GenerateContentConfig{
            Tools: []*genai.Tool{
                {CodeExecution: &genai.ToolCodeExecution{}},
            },
        }

        chat, _ := client.Chats.Create(
            ctx,
            "gemini-2.5-flash",
            config,
            nil,
        )

        result, _ := chat.SendMessage(
                        ctx,
                        genai.Part{Text: "What is the sum of the first 50 prime numbers? " +
                                              "Generate and run code for the calculation, and " +
                                              "make sure you get all 50.",
                                  },
                    )

        fmt.Println(result.Text())
        fmt.Println(result.ExecutableCode())
        fmt.Println(result.CodeExecutionResult())
    }

### REST

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" \
    -H "x-goog-api-key: $GEMINI_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{"tools": [{"code_execution": {}}],
        "contents": [
            {
                "role": "user",
                "parts": [{
                    "text": "Can you print \"Hello world!\"?"
                }]
            },{
                "role": "model",
                "parts": [
                  {
                    "text": ""
                  },
                  {
                    "executable_code": {
                      "language": "PYTHON",
                      "code": "\nprint(\"hello world!\")\n"
                    }
                  },
                  {
                    "code_execution_result": {
                      "outcome": "OUTCOME_OK",
                      "output": "hello world!\n"
                    }
                  },
                  {
                    "text": "I have printed \"hello world!\" using the provided python code block. \n"
                  }
                ],
            },{
                "role": "user",
                "parts": [{
                    "text": "What is the sum of the first 50 prime numbers? Generate and run code for the calculation, and make sure you get all 50."
                }]
            }
        ]
    }'

## Input/output (I/O)

Starting with[Gemini 2.0 Flash](https://ai.google.dev/gemini-api/docs/models/gemini#gemini-2.0-flash), code execution supports file input and graph output. Using these input and output capabilities, you can upload CSV and text files, ask questions about the files, and have[Matplotlib](https://matplotlib.org/)graphs generated as part of the response. The output files are returned as inline images in the response.

### I/O pricing

When using code execution I/O, you're charged for input tokens and output tokens:

**Input tokens:**

- User prompt

**Output tokens:**

- Code generated by the model
- Code execution output in the code environment
- Thinking tokens
- Summary generated by the model

### I/O details

When you're working with code execution I/O, be aware of the following technical details:

- The maximum runtime of the code environment is 30 seconds.
- If the code environment generates an error, the model may decide to regenerate the code output. This can happen up to 5 times.
- The maximum file input size is limited by the model token window. In AI Studio, using Gemini Flash 2.0, the maximum input file size is 1 million tokens (roughly 2MB for text files of the supported input types). If you upload a file that's too large, AI Studio won't let you send it.
- Code execution works best with text and CSV files.
- The input file can be passed in`part.inlineData`or`part.fileData`(uploaded via the[Files API](https://ai.google.dev/gemini-api/docs/files)), and the output file is always returned as`part.inlineData`.

|                                                                                         |                     Single turn                     |         Bidirectional (Multimodal Live API)         |
|-----------------------------------------------------------------------------------------|-----------------------------------------------------|-----------------------------------------------------|
| Models supported                                                                        | All Gemini 2.0 and 2.5 models                       | Only Flash experimental models                      |
| File input types supported                                                              | .png, .jpeg, .csv, .xml, .cpp, .java, .py, .js, .ts | .png, .jpeg, .csv, .xml, .cpp, .java, .py, .js, .ts |
| Plotting libraries supported                                                            | Matplotlib, seaborn                                 | Matplotlib, seaborn                                 |
| [Multi-tool use](https://ai.google.dev/gemini-api/docs/function-calling#multi-tool-use) | Yes (code execution + grounding only)               | Yes                                                 |

## Billing

There's no additional charge for enabling code execution from the Gemini API. You'll be billed at the current rate of input and output tokens based on the Gemini model you're using.

Here are a few other things to know about billing for code execution:

- You're only billed once for the input tokens you pass to the model, and you're billed for the final output tokens returned to you by the model.
- Tokens representing generated code are counted as output tokens. Generated code can include text and multimodal output like images.
- Code execution results are also counted as output tokens.

The billing model is shown in the following diagram:

![code execution billing model](https://ai.google.dev/static/gemini-api/docs/images/code-execution-diagram.png)

- You're billed at the current rate of input and output tokens based on the Gemini model you're using.
- If Gemini uses code execution when generating your response, the original prompt, the generated code, and the result of the executed code are labeled*intermediate tokens* and are billed as*input tokens*.
- Gemini then generates a summary and returns the generated code, the result of the executed code, and the final summary. These are billed as*output tokens*.
- The Gemini API includes an intermediate token count in the API response, so you know why you're getting additional input tokens beyond your initial prompt.

## Limitations

- The model can only generate and execute code. It can't return other artifacts like media files.
- In some cases, enabling code execution can lead to regressions in other areas of model output (for example, writing a story).
- There is some variation in the ability of the different models to use code execution successfully.

## Supported tools combinations

Code execution tool can be combined with[Grounding with Google Search](https://ai.google.dev/gemini-api/docs/google-search)to power more complex use cases.

## Supported libraries

The code execution environment includes the following libraries:

- attrs
- chess
- contourpy
- fpdf
- geopandas
- imageio
- jinja2
- joblib
- jsonschema
- jsonschema-specifications
- lxml
- matplotlib
- mpmath
- numpy
- opencv-python
- openpyxl
- packaging
- pandas
- pillow
- protobuf
- pylatex
- pyparsing
- PyPDF2
- python-dateutil
- python-docx
- python-pptx
- reportlab
- scikit-learn
- scipy
- seaborn
- six
- striprtf
- sympy
- tabulate
- tensorflow
- toolz
- xlrd

You can't install your own libraries.
| **Note:** Only`matplotlib`is supported for graph rendering using code execution.

## What's next

- Try the[code execution Colab](https://colab.research.google.com/github/google-gemini/cookbook/blob/main/quickstarts/Code_Execution.ipynb).
- Learn about other Gemini API tools:
  - [Function calling](https://ai.google.dev/gemini-api/docs/function-calling)
  - [Grounding with Google Search](https://ai.google.dev/gemini-api/docs/grounding)
  <br />

PythonJavaScriptGoREST

In a typical AI workflow, you might pass the same input tokens over and over to a model. The Gemini API offers two different caching mechanisms:

- Implicit caching (automatically enabled on most Gemini models, no cost saving guarantee)
- Explicit caching (can be manually enabled on most models, cost saving guarantee)

Explicit caching is useful in cases where you want to guarantee cost savings, but with some added developer work.

## Implicit caching

Implicit caching is enabled by default and available for most Gemini models. We automatically pass on cost savings if your request hits caches. There is nothing you need to do in order to enable this. It is effective as of May 8th, 2025. The minimum input token count for context caching is listed in the following table for each model:

|         Model          | Min token limit |
|------------------------|-----------------|
| Gemini 3 Flash Preview | 1024            |
| Gemini 3 Pro Preview   | 4096            |
| Gemini 2.5 Flash       | 1024            |
| Gemini 2.5 Pro         | 4096            |

To increase the chance of an implicit cache hit:

- Try putting large and common contents at the beginning of your prompt
- Try to send requests with similar prefix in a short amount of time

You can see the number of tokens which were cache hits in the response object's`usage_metadata`field.

## Explicit caching

Using the Gemini API explicit caching feature, you can pass some content to the model once, cache the input tokens, and then refer to the cached tokens for subsequent requests. At certain volumes, using cached tokens is lower cost than passing in the same corpus of tokens repeatedly.

When you cache a set of tokens, you can choose how long you want the cache to exist before the tokens are automatically deleted. This caching duration is called the*time to live*(TTL). If not set, the TTL defaults to 1 hour. The cost for caching depends on the input token size and how long you want the tokens to persist.

This section assumes that you've installed a Gemini SDK (or have curl installed) and that you've configured an API key, as shown in the[quickstart](https://ai.google.dev/gemini-api/docs/quickstart).

### Generate content using a cache

The following example shows how to generate content using a cached system instruction and video file.  

### Videos

    import os
    import pathlib
    import requests
    import time

    from google import genai
    from google.genai import types

    client = genai.Client()

    # Download video file
    url = 'https://storage.googleapis.com/generativeai-downloads/data/SherlockJr._10min.mp4'
    path_to_video_file = pathlib.Path('SherlockJr._10min.mp4')
    if not path_to_video_file.exists():
      with path_to_video_file.open('wb') as wf:
        response = requests.get(url, stream=True)
        for chunk in response.iter_content(chunk_size=32768):
          wf.write(chunk)

    # Upload the video using the Files API
    video_file = client.files.upload(file=path_to_video_file)

    # Wait for the file to finish processing
    while video_file.state.name == 'PROCESSING':
      print('Waiting for video to be processed.')
      time.sleep(2)
      video_file = client.files.get(name=video_file.name)

    print(f'Video processing complete: {video_file.uri}')

    # You must use an explicit version suffix: "-flash-001", not just "-flash".
    model='models/gemini-2.0-flash-001'

    # Create a cache with a 5 minute TTL
    cache = client.caches.create(
        model=model,
        config=types.CreateCachedContentConfig(
          display_name='sherlock jr movie', # used to identify the cache
          system_instruction=(
              'You are an expert video analyzer, and your job is to answer '
              'the user\'s query based on the video file you have access to.'
          ),
          contents=[video_file],
          ttl="300s",
      )
    )

    # Construct a GenerativeModel which uses the created cache.
    response = client.models.generate_content(
      model = model,
      contents= (
        'Introduce different characters in the movie by describing '
        'their personality, looks, and names. Also list the timestamps '
        'they were introduced for the first time.'),
      config=types.GenerateContentConfig(cached_content=cache.name)
    )

    print(response.usage_metadata)

    # The output should look something like this:
    #
    # prompt_token_count: 696219
    # cached_content_token_count: 696190
    # candidates_token_count: 214
    # total_token_count: 696433

    print(response.text)

### PDFs

    from google import genai
    from google.genai import types
    import io
    import httpx

    client = genai.Client()

    long_context_pdf_path = "https://www.nasa.gov/wp-content/uploads/static/history/alsj/a17/A17_FlightPlan.pdf"

    # Retrieve and upload the PDF using the File API
    doc_io = io.BytesIO(httpx.get(long_context_pdf_path).content)

    document = client.files.upload(
      file=doc_io,
      config=dict(mime_type='application/pdf')
    )

    model_name = "gemini-2.0-flash-001"
    system_instruction = "You are an expert analyzing transcripts."

    # Create a cached content object
    cache = client.caches.create(
        model=model_name,
        config=types.CreateCachedContentConfig(
          system_instruction=system_instruction,
          contents=[document],
        )
    )

    # Display the cache details
    print(f'{cache=}')

    # Generate content using the cached prompt and document
    response = client.models.generate_content(
      model=model_name,
      contents="Please summarize this transcript",
      config=types.GenerateContentConfig(
        cached_content=cache.name
      ))

    # (Optional) Print usage metadata for insights into the API call
    print(f'{response.usage_metadata=}')

    # Print the generated text
    print('\n\n', response.text)

### List caches

It's not possible to retrieve or view cached content, but you can retrieve cache metadata (`name`,`model`,`display_name`,`usage_metadata`,`create_time`,`update_time`, and`expire_time`).

To list metadata for all uploaded caches, use`CachedContent.list()`:  

    for cache in client.caches.list():
      print(cache)

To fetch the metadata for one cache object, if you know its name, use`get`:  

    client.caches.get(name=name)

### Update a cache

You can set a new`ttl`or`expire_time`for a cache. Changing anything else about the cache isn't supported.

The following example shows how to update the`ttl`of a cache using`client.caches.update()`.  

    from google import genai
    from google.genai import types

    client.caches.update(
      name = cache.name,
      config  = types.UpdateCachedContentConfig(
          ttl='300s'
      )
    )

To set the expiry time, it will accepts either a`datetime`object or an ISO-formatted datetime string (`dt.isoformat()`, like`2025-01-27T16:02:36.473528+00:00`). Your time must include a time zone (`datetime.utcnow()`doesn't attach a time zone,`datetime.now(datetime.timezone.utc)`does attach a time zone).  

    from google import genai
    from google.genai import types
    import datetime

    # You must use a time zone-aware time.
    in10min = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)

    client.caches.update(
      name = cache.name,
      config  = types.UpdateCachedContentConfig(
          expire_time=in10min
      )
    )

### Delete a cache

The caching service provides a delete operation for manually removing content from the cache. The following example shows how to delete a cache:  

    client.caches.delete(cache.name)

### Explicit caching using the OpenAI library

If you're using an[OpenAI library](https://ai.google.dev/gemini-api/docs/openai), you can enable explicit caching using the`cached_content`property on[`extra_body`](https://ai.google.dev/gemini-api/docs/openai#extra-body).

## When to use explicit caching

Context caching is particularly well suited to scenarios where a substantial initial context is referenced repeatedly by shorter requests. Consider using context caching for use cases such as:

- Chatbots with extensive[system instructions](https://ai.google.dev/gemini-api/docs/system-instructions)
- Repetitive analysis of lengthy video files
- Recurring queries against large document sets
- Frequent code repository analysis or bug fixing

### How explicit caching reduces costs

Context caching is a paid feature designed to reduce overall operational costs. Billing is based on the following factors:

1. **Cache token count:**The number of input tokens cached, billed at a reduced rate when included in subsequent prompts.
2. **Storage duration:**The amount of time cached tokens are stored (TTL), billed based on the TTL duration of cached token count. There are no minimum or maximum bounds on the TTL.
3. **Other factors:**Other charges apply, such as for non-cached input tokens and output tokens.

For up-to-date pricing details, refer to the Gemini API[pricing page](https://ai.google.dev/pricing). To learn how to count tokens, see the[Token guide](https://ai.google.dev/gemini-api/docs/tokens).

### Additional considerations

Keep the following considerations in mind when using context caching:

- The*minimum* input token count for context caching varies by model. The*maximum* is the same as the maximum for the given model. (For more on counting tokens, see the[Token guide](https://ai.google.dev/gemini-api/docs/tokens)).
- The model doesn't make any distinction between cached tokens and regular input tokens. Cached content is a prefix to the prompt.
- There are no special rate or usage limits on context caching; the standard rate limits for`GenerateContent`apply, and token limits include cached tokens.
- The number of cached tokens is returned in the`usage_metadata`from the create, get, and list operations of the cache service, and also in`GenerateContent`when using the cache.

# PLOS Gemini API Integration Guide

## Overview

This guide covers integrating Google Gemini API into PLOS for AI-powered features. Gemini offers:
- Text generation & analysis
- Vision capabilities (image understanding)
- Code execution
- Structured outputs
- Function calling
- Document processing

---

## 1. Model Selection for PLOS

### Recommended Models by Use Case

| Use Case | Model | Reason |
|----------|-------|--------|
| **Journal Parsing** | `gemini-2.5-flash` | Fast, cost-effective for text extraction |
| **Context Analysis** | `gemini-2.5-flash` | Balanced performance for reasoning |
| **Vision** | `gemini-2.5-flash-image` | Image understanding and multimodal analysis |
| **Code Generation** | `gemini-2.5-pro` | Better reasoning for complex tasks |
| **Document Processing** | `gemini-2.5-flash` | Handles PDFs (up to 1000 pages) |
| **Complex Reasoning** | `gemini-3-flash-preview` | Latest, improved reasoning |

**For PLOS, use: `gemini-2.5-flash` as default** (fastest, cheapest, good quality)

---

## 2. Core Features for PLOS

### A. Text Generation & Extraction

**Use Case:** Journal parsing, insight generation, recommendations

```python
from google import genai
from google.genai import types

client = genai.Client(api_key="GEMINI_API_KEY")

# Simple text generation
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Analyze this journal entry: 'Had a great run today, feeling energized'"
)

print(response.text)
```

### B. Structured Outputs (JSON)

**Use Case:** Extract structured data from journal entries, format recommendations

```python
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

class JournalEntry(BaseModel):
    mood_score: int = Field(description="Mood from 1-10")
    energy_level: int
    exercise: str
    sleep_hours: float
    tags: list[str]

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Parse: 'Slept 8 hours, went for a run, feeling great, mood 8/10'",
    config={
        "response_mime_type": "application/json",
        "response_json_schema": JournalEntry.model_json_schema(),
    }
)

# Returns valid JSON matching schema
entry = JournalEntry.model_validate_json(response.text)
```

### C. Vision Capabilities

**Use Case:** Knowledge system - extract from images, screenshots, photos

```python
import base64
from google import genai
from google.genai import types

# Option 1: From local file
with open('image.jpg', 'rb') as f:
    image_bytes = f.read()

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
        types.Part.from_bytes(
            data=image_bytes,
            mime_type='image/jpeg',
        ),
        'Extract all text and tables from this image'
    ]
)

# Option 2: From URL
import requests
image_bytes = requests.get("https://example.com/image.jpg").content
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
        types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
        'Describe what you see'
    ]
)
```

### D. Function Calling (Tool Use)

**Use Case:** Let Claude decide which functions to call for insights, scheduling, etc.

```python
from google import genai
from google.genai import types

# Define tools
tools = {
    "name": "get_user_correlations",
    "description": "Get correlations between mood and sleep",
    "parameters": {
        "type": "object",
        "properties": {
            "metric1": {"type": "string"},
            "metric2": {"type": "string"}
        },
        "required": ["metric1", "metric2"]
    }
}

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="What's the correlation between my sleep and mood?",
    config=types.GenerateContentConfig(
        tools=[types.Tool(function_declarations=[tools])]
    )
)

# Check if Claude called a function
if response.candidates[0].content.parts[0].function_call:
    func_call = response.candidates[0].content.parts[0].function_call
    print(f"Function: {func_call.name}")
    print(f"Args: {func_call.args}")
    # YOUR CODE: Execute the function and return results
```

### E. Document Processing (PDFs)

**Use Case:** Knowledge system - process user-uploaded PDFs (up to 1000 pages)

```python
from google import genai
from google.genai import types
import pathlib

client = genai.Client()

# Upload PDF using Files API
file_path = pathlib.Path('document.pdf')
pdf_file = client.files.upload(
    file=file_path,
    config={"mime_type": "application/pdf"}
)

# Use in content generation
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
        pdf_file,
        "Summarize this document and extract key points"
    ]
)

print(response.text)
```

### F. Code Execution

**Use Case:** Let Gemini write and execute Python code for calculations, data analysis

```python
from google import genai
from google.genai import types

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="What's the sum of first 50 prime numbers? Generate and run code.",
    config=types.GenerateContentConfig(
        tools=[types.Tool(code_execution=types.ToolCodeExecution)]
    )
)

# Response includes: text, executable_code, code_execution_result
for part in response.candidates[0].content.parts:
    if part.text:
        print("Text:", part.text)
    if part.executable_code:
        print("Code:", part.executable_code.code)
    if part.code_execution_result:
        print("Result:", part.code_execution_result.output)
```

---

## 3. PLOS-Specific Integration Patterns

### Pattern 1: Journal Entry Parser Service

```python
# services/journal-parser/src/parser.py
from google import genai
from google.genai import types
from pydantic import BaseModel

class ParsedEntry(BaseModel):
    mood: int
    energy: int
    sleep_hours: float
    exercise: str
    nutrition: str
    work_focus: int
    tags: list[str]

class JournalParser:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
    
    def parse_entry(self, raw_text: str) -> ParsedEntry:
        """Parse journal entry using Gemini with structured output"""
        
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"Parse this journal entry:\n{raw_text}",
            config={
                "response_mime_type": "application/json",
                "response_json_schema": ParsedEntry.model_json_schema(),
            }
        )
        
        return ParsedEntry.model_validate_json(response.text)
    
    def detect_gaps(self, raw_text: str) -> list[str]:
        """Identify missing information in journal entry"""
        
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"""Analyze this journal entry and identify what important 
            health metrics are missing. Return as JSON list.
            
            Entry: {raw_text}""",
            config={
                "response_mime_type": "application/json",
                "response_json_schema": {
                    "type": "object",
                    "properties": {
                        "missing_metrics": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    }
                }
            }
        )
        
        return json.loads(response.text)["missing_metrics"]
```

### Pattern 2: Insight Agent (Tool Calling)

```python
# services/agents/insight-agent/src/main.py
from google import genai
from google.genai import types

class InsightAgent:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
    
    def generate_insights(self, context: dict) -> str:
        """Generate personalized insights using tool calling"""
        
        tools = [
            {
                "name": "query_correlations",
                "description": "Get correlations between user metrics",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "metric1": {"type": "string"},
                        "metric2": {"type": "string"}
                    },
                    "required": ["metric1", "metric2"]
                }
            },
            {
                "name": "get_trends",
                "description": "Get 7-day trend for a metric",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "metric": {"type": "string"}
                    },
                    "required": ["metric"]
                }
            }
        ]
        
        messages = [
            {
                "role": "user",
                "content": f"""Analyze user data and generate insights:
                Current mood: {context['mood']}
                Sleep: {context['sleep']} hours
                Exercise: {context['exercise']} mins
                
                Use available tools to find correlations and trends."""
            }
        ]
        
        # Agentic loop
        while True:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=messages,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(function_declarations=tools)]
                )
            )
            
            # Check if done
            if response.stop_reason == "end_turn":
                return response.content[-1].text
            
            # Process tool calls
            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        # YOUR CODE: Execute the tool
                        result = self._execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result)
                        })
                
                messages.append({"role": "user", "content": tool_results})
    
    def _execute_tool(self, tool_name: str, tool_input: dict):
        # Connect to your actual tools/services
        if tool_name == "query_correlations":
            # Call correlation engine service
            return {"correlation": 0.75, "impact": "+30%"}
        elif tool_name == "get_trends":
            # Call trend analyzer
            return {"trend": "improving", "datapoints": [6, 6.2, 6.5]}
```

### Pattern 3: Knowledge Extraction

```python
# services/journal-parser/src/extraction_engine.py
from google import genai
from google.genai import types

class KnowledgeExtractor:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
    
    def extract_from_url(self, url: str) -> dict:
        """Extract structured data from a URL"""
        
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                f"Analyze this URL and extract key information: {url}",
            ]
        )
        
        # Parse and structure the response
        return {
            "source_url": url,
            "title": "",  # Extract from response
            "summary": response.text,
            "tags": [],  # Extract categories
            "reading_time": 0  # Estimate
        }
    
    def extract_from_image(self, image_path: str) -> dict:
        """Extract text and structured data from image"""
        
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type='image/jpeg'
                ),
                """Extract all text, tables, and diagrams from this image.
                Return as JSON with: extracted_text, tables, diagrams_description"""
            ],
            config={
                "response_mime_type": "application/json",
                "response_json_schema": {
                    "type": "object",
                    "properties": {
                        "extracted_text": {"type": "string"},
                        "tables": {"type": "array"},
                        "diagrams": {"type": "string"}
                    }
                }
            }
        )
        
        return json.loads(response.text)
```

---

## 4. Token Management & Costs

### Token Counting

```python
# Estimate tokens in your content
def estimate_tokens(text: str) -> int:
    """Rough estimate: ~4 chars per token"""
    return len(text) // 4

# For images
# - Images under 384x384 pixels: 258 tokens
# - Larger images: tiled into 768x768 pixels, each tile = 258 tokens

# For PDFs
# - Each page: 258 tokens (as image)
```

### Cost Optimization

1. **Use `gemini-2.5-flash`** for most operations (cheapest)
2. **Batch requests** - combine multiple queries
3. **Cache repeated context** - use explicit caching for PDFs, system instructions

```python
# Explicit caching example
cache = client.caches.create(
    model="gemini-2.5-flash",
    config=types.CreateCachedContentConfig(
        system_instruction="You are a wellness analyst",
        contents=[large_document_or_pdf],
        ttl="3600s"  # 1 hour
    )
)

# Use cache for subsequent requests
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Analyze the cached document",
    config=types.GenerateContentConfig(cached_content=cache.name)
)
```

---

## 5. Environment Configuration

### .env Setup

```env
# Gemini API
GEMINI_API_KEY=your-api-key-here

# Service Configuration
JOURNAL_PARSER_ENABLED=true
KNOWLEDGE_EXTRACTION_ENABLED=true
INSIGHT_AGENT_ENABLED=true

# Model Selection
GEMINI_DEFAULT_MODEL=gemini-2.5-flash
GEMINI_VISION_MODEL=gemini-2.5-flash-image

# Feature Flags
USE_GEMINI_CACHING=true
ENABLE_CODE_EXECUTION=true
```

### Docker Setup

```dockerfile
# Add to service Dockerfile
FROM python:3.11-slim

RUN pip install google-genai

ENV GEMINI_API_KEY=${GEMINI_API_KEY}
```

---

## 6. Error Handling

```python
from anthropic import APIError, APIConnectionError
import time

def safe_gemini_call(func, max_retries=3, backoff_factor=2):
    """Retry logic for Gemini API calls"""
    
    for attempt in range(max_retries):
        try:
            return func()
        except APIConnectionError as e:
            if attempt == max_retries - 1:
                raise
            wait_time = backoff_factor ** attempt
            print(f"Connection error, retrying in {wait_time}s...")
            time.sleep(wait_time)
        except APIError as e:
            print(f"API error: {e}")
            raise

# Usage
def parse_journal():
    return client.models.generate_content(...)

result = safe_gemini_call(parse_journal)
```

---

## 7. Gemini Models Comparison for PLOS

| Feature | 2.5 Flash | 2.5 Pro | 3 Flash Preview |
|---------|-----------|---------|-----------------|
| **Speed** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Cost** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Reasoning** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Vision** | ✓ | ✓ | ✓ |
| **Function Calling** | ✓ | ✓ | ✓ |
| **Code Execution** | ✓ | ✓ | ✓ |
| **Document (PDF)** | ✓ | ✓ | ✓ |
| **Max Input Tokens** | 1M | 1M | 1M |

**Recommendation for PLOS:** Start with `gemini-2.5-flash`, upgrade to `gemini-3-flash-preview` when available for better reasoning.

---

## 8. Implementation Roadmap

### Phase 1 (Week 1-2)
- [ ] Set up Gemini API client
- [ ] Implement journal parser with structured outputs
- [ ] Add gap detection

### Phase 2 (Week 3-4)
- [ ] Implement insight agent with function calling
- [ ] Connect to correlation engine
- [ ] Add caching for context

### Phase 3 (Week 5-6)
- [ ] Knowledge system with vision & document extraction
- [ ] Image/PDF processing
- [ ] Semantic search integration

### Phase 4 (Week 7-8)
- [ ] Code execution for calculations
- [ ] Advanced agents (scheduling, motivation)
- [ ] Performance optimization & caching

---

## 9. Useful Links

- [Gemini API Docs](https://ai.google.dev/gemini-api/docs)
- [Model Overview](https://ai.google.dev/gemini-api/docs/models)
- [Python SDK](https://github.com/google-gemini/python-client)
- [Pricing Calculator](https://ai.google.dev/pricing)
- [Cookbook Examples](https://github.com/google-gemini/cookbook)

---

## Quick Reference

```python
# Always import this way
from google import genai
from google.genai import types

# Create client
client = genai.Client(api_key="YOUR_KEY")

# Simple generation
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Your prompt here"
)
print(response.text)

# Check token usage
print(response.usage_metadata)
```

Start with `gemini-2.5-flash` and scale up as needed! 🚀