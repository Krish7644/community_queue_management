<?php
// Offline rendering fixture only: no HTTP session or database calls.
$project = dirname(__DIR__);
$legacy = getenv('LEGACY_REFERENCE_ROOT');
if (!$legacy) throw new RuntimeException('Set LEGACY_REFERENCE_ROOT to the original checkout.');
define('ROOT_PATH', $legacy);
define('PUBLIC_PATH', $legacy.'/public');
define('CARD_PATH', $project.'/backend/media/template-comparison/php');
define('BASE_URL', 'http://127.0.0.1');
if (!is_dir(CARD_PATH)) mkdir(CARD_PATH, 0755, true);
require ROOT_PATH.'/app/Core.php';
require ROOT_PATH.'/app/CardService.php';
require ROOT_PATH.'/app/HodFeatures.php';
require ROOT_PATH.'/app/VvipFeatures.php';
$token = str_repeat('a', 64);
$pass = ['id'=>99991,'pass_code'=>'H5-99991-0001','pass_type'=>'FIVE_MEMBER','token'=>$token,'authority_name'=>'Sample HOD','recipient_name'=>'Sample Devotee'];
copy(compose_hod_pass_card($pass,false), CARD_PATH.'/hod.png');
$pass['pass_code']='CG-99991-0001';$pass['authority_name']='Sample Congregation';
copy(compose_hod_pass_card($pass,false), CARD_PATH.'/combined.png');
$vvip=['id'=>99992,'pass_id'=>'V5-99991-0001','guest_name'=>'Sample Devotee','recipient_name'=>'Sample Devotee','token'=>$token];
copy(vvip_card_file($vvip), CARD_PATH.'/vvip.png');
$vvip['pass_id']='VOL-99991-0001';
copy(volunteer_legacy_card_file($vvip), CARD_PATH.'/volunteer.png');
$member=['id'=>99993,'name'=>'Sample Devotee','devotee_id'=>'99993','photo_path'=>null,'admin_id'=>null,'authority_type'=>'HOD','authority_profile_type'=>null,'token'=>$token];
copy(card_compose_image($member,make_member_qr($member)), CARD_PATH.'/member.png');
echo "Offline original-template reference images generated.\n";
