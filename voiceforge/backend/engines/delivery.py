"""Direct model-supported performance; never emulate emotions with playback tricks."""
DIRECTIONS={
 'neutral':'Speak naturally and conversationally, with varied emphasis and phrasing. Avoid a flat announcer cadence.',
 'afraid':'Sound genuinely afraid. Use a tense, slightly unsteady voice with cautious pauses and urgent emphasis.',
 'terrified':'Sound terrified and close to panic, with trembling breath and urgent, broken phrasing. Keep every word intelligible.',
 'angry':'Deliver controlled anger: sharp consonants, tense energy, strong emphasis and purposeful pauses.',
 'aggressive':'Deliver a forceful, confrontational warning, with a gritty edge and emphatic stresses. Sound ready for a fight, not like a narrator.',
 'sad':'Speak with quiet sorrow, weighted pauses and a subdued, vulnerable tone.',
 'exhausted':'Sound physically exhausted, with breathy effort, uneven pauses and fading energy.',
 'suspicious':'Sound guarded and skeptical, with questioning inflections and deliberate emphasis on doubtful words.',
 'confident':'Speak with warm conviction, lively phrasing and decisive emphasis.',
 'arrogant':'Sound smug and superior, with measured pacing and dismissive, pointed emphasis.',
 'whispering':'Whisper closely and urgently, quietly but intelligibly, preserving the speaker identity.',
 'crying':'Sound tearful, with a wavering voice and restrained sobbing between phrases. Keep the spoken words clear.',
 'laughing':'Speak with amused, smiling energy and light chuckles between phrases, keeping the dialogue intelligible.',
 'injured':'Sound hurt and strained, with interrupted breath and pained effort, while speaking clearly.',
 'dying':'Speak weakly with labored breath and fading strength, using meaningful pauses while retaining intelligibility.'}

def delivery_instruction(emotion,notes=''):
    if emotion not in DIRECTIONS: raise ValueError('Unknown emotion.')
    if not isinstance(notes,str) or len(notes)>1000: raise ValueError('Performance direction must be at most 1000 characters.')
    return DIRECTIONS[emotion]+(' Actor direction: '+notes.strip() if notes.strip() else '')
