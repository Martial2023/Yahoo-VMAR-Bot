import prisma from "@/lib/prisma";


// ----------------------------------------------------------------------------
// AI prompts — shared baseline (a platform can override via PlatformSettings)
// ----------------------------------------------------------------------------

const REPLY_PROMPT = `Tu es un investisseur passionné par les technologies marines électriques et particulièrement par Vision Marine Technologies (VMAR, NASDAQ). Tu participes aux discussions sur Yahoo Finance.

Règles :
- Réponds en anglais, de manière naturelle et conversationnelle (2-3 phrases max)
- Sois informatif mais jamais agressif
- Ne donne JAMAIS de conseil financier direct (pas de "buy", "sell", "invest")
- Tu peux mentionner des faits publics sur VMAR (produits, partenariats, résultats)
- Varie ton style : parfois pose une question, parfois partage un fait, parfois donne ton opinion mesurée
- N'utilise PAS de hashtags, d'émojis excessifs, ni de langage promotionnel
- Ne mentionne JAMAIS que tu es un bot ou une IA
- Sois bref et naturel, comme un vrai utilisateur Yahoo Finance`;

const POST_PROMPT = `Tu es un investisseur passionné par les technologies marines électriques et particulièrement par Vision Marine Technologies (VMAR, NASDAQ). Tu participes aux discussions sur Yahoo Finance.

Règles :
- Écris en anglais un commentaire qui initie une discussion (2-3 phrases max)
- Tu peux : poser une question ouverte à la communauté, partager une observation sur le marché des bateaux électriques, mentionner un fait public récent sur VMAR
- Sois naturel et conversationnel, comme un vrai investisseur retail
- Ne donne JAMAIS de conseil financier direct (pas de "buy", "sell", "invest")
- N'utilise PAS de hashtags, d'émojis excessifs, ni de langage promotionnel
- Ne mentionne JAMAIS que tu es un bot ou une IA
- Varie les sujets : technologie, marché, compétition, résultats financiers, partenariats`;

const REDDIT_REPLY_PROMPT = `${REPLY_PROMPT}

Spécifique à Reddit :
- Adopte le ton de la communauté (plus décontracté que Yahoo Finance)
- Pas plus de 4 phrases, idéalement 2-3
- Aucune signature, aucun lien promotionnel
- Respecte les règles du subreddit (pas de pump, pas de "to the moon")`;

const REDDIT_POST_PROMPT = `${POST_PROMPT}

Spécifique à Reddit :
- Le post doit pouvoir servir de starter de discussion sur r/pennystocks ou r/stocks
- Pas plus de 4 phrases, idéalement 2-3
- Pas de titre dans le corps (le titre est généré séparément)`;


async function main() {
  // --- Global settings (singleton) ---------------------------------------
  await prisma.botSettings.upsert({
    where: { id: 1 },
    update: {},
    create: {
      id: 1,
      replyPrompt: REPLY_PROMPT,
      postPrompt: POST_PROMPT,
    },
  });
  console.log("✓ bot_settings seeded (id=1)");

  // --- Yahoo Finance platform (existing behaviour preserved) -------------
  await prisma.platformSettings.upsert({
    where: { platform: "yahoo_finance" },
    update: {},
    create: {
      platform: "yahoo_finance",
      displayName: "Yahoo Finance",
      enabled: true,                       // already in production
      mode: "production",                  // keep current behaviour
      replyEnabled: true,
      postEnabled: true,
      ticker: "VMAR",
      maxRepliesPerDay: 10,
      maxPostsPerDay: 3,
      minPostLength: 20,
      scheduleSlots: ["09:00", "14:00", "19:00"],
      scheduleJitterMin: 10,
      replyPrompt: REPLY_PROMPT,
      postPrompt: POST_PROMPT,
      config: {
        skipAuthors: ["vision marine", "vision56508"],
      },
    },
  });
  console.log("✓ platform_settings.yahoo_finance seeded");

  // --- Reddit platform (disabled by default — run login_reddit.py first) ---
  await prisma.platformSettings.upsert({
    where: { platform: "reddit" },
    update: {},
    create: {
      platform: "reddit",
      displayName: "Reddit",
      enabled: false,                      // off until session is set up
      mode: "test",                        // start safely — whitelist only
      replyEnabled: true,
      postEnabled: false,                  // no dedicated VMAR subreddit
      ticker: "VMAR",
      maxRepliesPerDay: 10,
      maxPostsPerDay: 0,
      minPostLength: 30,
      scheduleSlots: ["10:00", "16:00"],
      scheduleJitterMin: 15,
      replyPrompt: REDDIT_REPLY_PROMPT,
      postPrompt: REDDIT_POST_PROMPT,
      config: {
        searchQueries: ["VMAR", "Vision Marine", "Vision Marine Technologies"],
        maxPostsPerSearch: 5,              // max posts to visit per cycle
        skipAuthors: ["automoderator"],
      },
    },
  });
  console.log("✓ platform_settings.reddit seeded (disabled — run login_reddit.py first)");

  // --- StockTwits platform (test mode — run login_stocktwits.py first) ---
  const STOCKTWITS_REPLY_PROMPT = `${REPLY_PROMPT}

Spécifique à StockTwits :
- Adopte le ton court et direct de StockTwits (2-3 phrases max)
- Tu peux mentionner le sentiment (bullish/bearish) de façon nuancée
- Pas de hashtags excessifs, 1-2 cashtags ($VMAR) max
- Pas de liens promotionnels ni de pump ("to the moon", "rocket", etc.)
- Reste factuel et conversationnel`;

  const STOCKTWITS_POST_PROMPT = `${POST_PROMPT}

Spécifique à StockTwits :
- Message court (2-3 phrases), style micro-blogging
- Commence par $VMAR pour le contexte
- Tu peux ajouter un sentiment (Bullish/Bearish) si pertinent
- Pas de pump, pas de "not financial advice"
- Varie les sujets : technologie, catalyseurs, volume, analyse technique simple`;

  await prisma.platformSettings.upsert({
    where: { platform: "stocktwits" },
    update: {},
    create: {
      platform: "stocktwits",
      displayName: "StockTwits",
      enabled: true,                      // off until session is set up
      mode: "test",                        // start safely — whitelist only
      replyEnabled: true,
      postEnabled: true,
      ticker: "VMAR",
      maxRepliesPerDay: 8,
      maxPostsPerDay: 3,
      minPostLength: 10,
      scheduleSlots: ["10:00", "13:00", "16:00"],
      scheduleJitterMin: 15,
      replyPrompt: STOCKTWITS_REPLY_PROMPT,
      postPrompt: STOCKTWITS_POST_PROMPT,
      config: {
        skipAuthors: ["visionmarineir", "networkNewswire"],
      },
    },
  });
  console.log("✓ platform_settings.stocktwits seeded (disabled — run login_stocktwits.py first)");
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
