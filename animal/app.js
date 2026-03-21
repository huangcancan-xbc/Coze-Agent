const promptInput = document.getElementById("promptInput");
const generateBtn = document.getElementById("generateBtn");
const clearBtn = document.getElementById("clearBtn");
const statusBox = document.getElementById("statusBox");
const videoBox = document.getElementById("videoBox");
const promptText = document.getElementById("promptText");
const botIdText = document.getElementById("botIdText");
const answerText = document.getElementById("answerText");
const followList = document.getElementById("followList");
const exampleChips = document.getElementById("exampleChips");
const botName = document.getElementById("botName");
const shareLink = document.getElementById("shareLink");

function setStatus(type, title, message) {
  statusBox.className = `status${type ? ` ${type}` : ""}`;
  statusBox.innerHTML = `<strong>${title}</strong><p>${message}</p>`;
}

function setLoading(loading) {
  generateBtn.disabled = loading;
  clearBtn.disabled = loading;
  generateBtn.textContent = loading ? "生成中..." : "开始生成";
}

function renderVideo(url) {
  videoBox.innerHTML = url
    ? `<video src="${url}" controls playsinline preload="metadata"></video>`
    : `<div class="video-placeholder">视频生成完成后会显示在这里</div>`;
}

function renderFollowUps(items) {
  followList.innerHTML = "";
  (items || []).forEach((item) => {
    const btn = document.createElement("button");
    btn.className = "follow-btn";
    btn.textContent = item;
    btn.addEventListener("click", () => {
      promptInput.value = item;
      promptInput.focus();
    });
    followList.appendChild(btn);
  });
}

async function loadConfig() {
  try {
    const response = await fetch("/api/config");
    const data = await response.json();
    if (!response.ok || !data.success) return;

    botName.textContent = data.bot_name;
    shareLink.href = data.share_url;

    exampleChips.innerHTML = "";
    (data.examples || []).forEach((example) => {
      const chip = document.createElement("button");
      chip.className = "chip";
      chip.textContent = example;
      chip.addEventListener("click", () => {
        promptInput.value = example;
        promptInput.focus();
      });
      exampleChips.appendChild(chip);
    });
  } catch (error) {
    setStatus("warn", "初始化提示", "配置加载失败，但你仍然可以直接输入描述进行尝试。");
  }
}

async function generateVideo() {
  const prompt = promptInput.value.trim();
  if (!prompt) {
    setStatus("error", "输入不能为空", "请先输入动物相关描述。");
    promptInput.focus();
    return;
  }

  setLoading(true);
  setStatus("", "正在生成", "Coze 智能体正在生成视频，请稍候。这类视频生成可能需要一点时间。");
  renderVideo("");

  try {
    const response = await fetch("/api/generate-video", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });

    const data = await response.json();
    if (!response.ok || !data.success) {
      throw new Error(data.error || "生成失败");
    }

    renderVideo(data.video_url);
    promptText.textContent = data.prompt;
    botIdText.textContent = data.bot_id;
    answerText.textContent = data.answer_text || "视频已生成。";
    renderFollowUps(data.follow_ups);
    setStatus("success", "生成成功", "视频已返回，你可以直接播放或换一个描述继续生成。");
  } catch (error) {
    const message = error.message || "生成失败";
    const statusType = message.includes("请求过大") ? "warn" : "error";
    setStatus(statusType, "生成失败", message);
    answerText.textContent = "如果经常失败，建议缩短描述，只保留动物、动作和场景三类信息。";
    botIdText.textContent = "未生成";
    renderFollowUps([]);
  } finally {
    setLoading(false);
  }
}

generateBtn.addEventListener("click", generateVideo);
clearBtn.addEventListener("click", () => {
  promptInput.value = "";
  promptInput.focus();
  renderVideo("");
  setStatus("", "已清空", "你可以重新输入新的动物视频描述。");
});

promptInput.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    generateVideo();
  }
});

loadConfig();
