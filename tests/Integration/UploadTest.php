<?php

declare(strict_types=1);

namespace Adshares\AdSelect\Tests\Integration;

use Adshares\AdSelect\Tests\Integration\Builders\CampaignBuilder;
use Symfony\Component\HttpFoundation\Response;

final class UploadTest extends IntegrationTestCase
{
    public function testUpdateCampaign(): void
    {
        $client = self::createClient();

        $client->request(
            'POST',
            '/api/v1/campaigns',
            [],
            [],
            [],
            json_encode(['campaigns' => [CampaignBuilder::default()]])
        );

        self::assertResponseIsSuccessful();
        self::assertTrue($this->indexExists('banners'));
        $documents = $this->documentsInIndex('banners');
        self::assertCount(1, $documents);
        $document = $documents[0];
        self::assertEquals('fedcba9876543210fedcba9876543210', $document['_id']);
        self::assertContains('728x90', $document['_source']['banner']['size']);
        self::assertContains('image', $document['_source']['banner']['keywords:type']);
        self::assertContains('crypto', $document['_source']['banner']['keywords:test_classifier:category']);
        self::assertContains('desktop', $document['_source']['filters:require:device:type']);
    }
}
